"""Base controller for Ember.js/JSON:API based components."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from abc import ABC
from asyncio import Task
from collections.abc import Awaitable, Callable, Iterator
from enum import Enum
from inspect import iscoroutinefunction
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar

from _pyalarmdotcomajax.const import ATTR_DESIRED_STATE, ATTR_STATE
from _pyalarmdotcomajax.events import (
    EventBrokerMessage,
    EventBrokerTopic,
    ResourceEventMessage,
)
from _pyalarmdotcomajax.exceptions import NotAuthorized, UnknownDevice
from _pyalarmdotcomajax.models.base import AdcResource
from _pyalarmdotcomajax.util import resources_pretty, resources_raw
from _pyalarmdotcomajax.websocket.client import (
    ConnectionEvent,
    RawResourceEventMessage,
    SupportedResourceEvents,
    WebSocketState,
)
from _pyalarmdotcomajax.websocket.messages import (
    BaseWSMessage,
    EventWSMessage,
    ResourceEventType,
)
from rich.console import Group

if TYPE_CHECKING:
    from _pyalarmdotcomajax import AlarmBridge
    from _pyalarmdotcomajax.models.base import ResourceType
    from _pyalarmdotcomajax.models.jsonapi import Resource

log = logging.getLogger(__name__)

# How many refreshes in a row a device must be missing from before it is unregistered. Unregistering removes its
# Home Assistant entities from the entity registry (and with them any names, areas and labels set on them), so one
# incomplete response must not be enough; a device really removed from the account goes after this many polls.
MISSING_REFRESHES_BEFORE_REMOVAL = 3

# Declared locally rather than imported from _pyalarmdotcomajax.models, even
# though it's the same conceptual type variable used throughout the codebase.
# This works around a known, longstanding mypy limitation (python/mypy#11854):
# a TypeVar imported from another module and used to parameterize a Generic[]
# class triggers a spurious "Free type variable expected in Generic[...]"
# error. Bound identically, so this remains fully type-compatible with every
# other file's own AdcResourceT usage (TypeVar bound-checking is structural,
# not based on object identity).
AdcResourceT = TypeVar("AdcResourceT", bound=AdcResource)

C = TypeVar("C", bound="BaseController")
# Deliberately a separate TypeVar from AdcResourceT (not just reused), even
# though they're conceptually related - reusing the exact same TypeVar object
# in this plain function's signature, positioned before BaseController's own
# class definition, confuses mypy into treating AdcResourceT as no longer
# "free" by the time it reaches `class BaseController(ABC, Generic[AdcResourceT])`
# below, causing a spurious "Free type variable expected in Generic[...]" error.
_ResourceClassT = TypeVar("_ResourceClassT", bound="AdcResource")


def device_controller(
    resource_type: ResourceType, resource_class: type[_ResourceClassT]
) -> Callable[[type[C]], type[C]]:
    """
    Simplify controller definitions by setting common attributes.

    Args:
        resource_type (ResourceType): The type of resource the controller manages.
        resource_class (type[AdcResourceT]): The class of the resource managed by the controller.

    Returns:
        type[BaseController[AdcResourceT]]: The decorated controller class.

    """

    def decorator(cls: type[C]) -> type[C]:
        cls.resource_type = resource_type
        cls._resource_class = resource_class
        cls._is_device_controller = True
        return cls

    return decorator


class BaseController(ABC, Generic[AdcResourceT]):
    """Base controller for Ember.js/JSON:API based components."""

    # ResourceTypes to be pulled from API response data object.
    resource_type: ClassVar[ResourceType]
    # AdcResource class to be created by this controller.
    _resource_class: type[AdcResourceT]
    # URL to be used for API requests when URL cannot be derived directly from controler's ResourceType.
    _resource_url_override: ClassVar[str | None] = None
    # Restricts this controller to specific device IDs. Some Alarm.com endpoints do not support "get all"
    # functions and require the user to specify target device IDs. This attribute allows the controller to
    # initialize without failing when the required `resource_ids` are not immediately available. For example,
    # this is used to initialize the DealersController, which requires `resource_ids` from the
    # IdentitiesController.
    _requires_target_ids: ClassVar[bool] = False
    # WebSocket events supported by this controller. This is used to declare which types of events
    # and property changes the controller should receive. To receive events, add ResourceEventType values
    # to the 'events' list. To receive property changes (like temperature changes), add ResourcePropertyChangeType
    # values to the 'property_changes' list. A controller must have this set to receive any real-time updates.
    _supported_resource_events: ClassVar[SupportedResourceEvents | None] = None
    _refresh_connection_states: ClassVar[frozenset[WebSocketState]] = frozenset({WebSocketState.RECONNECTED})
    # Maps websocket events to states.
    _event_state_map: ClassVar[MappingProxyType[ResourceEventType, Enum] | None] = None
    # Indicates whether this controller is a device controller.
    _is_device_controller: ClassVar[bool] = False
    # Persistent devices need deletion protection; temporary resources may override this.
    _missing_refreshes_before_removal: ClassVar[int] = MISSING_REFRESHES_BEFORE_REMOVAL

    def __init__(
        self,
        bridge: AlarmBridge,
        data_provider: BaseController | None = None,
        target_device_ids: list[str] | None = None,
    ) -> None:
        """Initialize base controller."""

        self._bridge = bridge

        # Tracks whether the controller has been initialized.
        self._initialized: bool = False

        # Tracks primary resources discovered by this controller.
        self._resources: dict[str, AdcResourceT] = {}

        # Tracks included resources discovered by this controller.
        self._included_resources: list[Resource] = []

        # If set, the current controller will depend on the data provider for API fetch updates.
        self._api_data_provider = data_provider
        self._api_data_unsubscribe: Callable | None = None

        # Dict of callbacks for controllers that depend on the current controller for API updates.
        # Receivers are sub-controllers' _refresh methods, called as callback(resources, fetch_started=...).
        self._api_data_receivers: dict[ResourceType, list[Callable[..., Awaitable | None]]] = {}

        # Restricts this controller to specific devices. Used for controllers that only support single-serve
        # endpoints.
        self._target_device_ids: set[str] = set(target_device_ids or [])
        self._has_no_devices = False

        # Holds references to asyncio tasks to prevent them from being garbage collected before completion.
        self._background_tasks: set[Task] = set()

        # When a WebSocket event last changed each resource (time.monotonic()). A refresh whose request was
        # sent before that moment carries an older snapshot and must not overwrite the event; see _refresh.
        self._last_event_at: dict[str, float] = {}

        # Consecutive refreshes each registered resource has been missing from; see MISSING_REFRESHES_BEFORE_REMOVAL.
        self._missing_refreshes: dict[str, int] = {}

    @property
    def items(self) -> list[AdcResourceT]:
        """Return all resources for this controller."""
        return list(self._resources.values())

    @property
    def is_device_controller(self) -> bool:
        """Return whether this controller is a device controller."""
        return self._is_device_controller

    ##################
    # INITIALIZATION #
    ##################

    @property
    def initialized(self) -> bool:
        """Return whether this controller has completed its one-time initialization."""

        return self._initialized

    async def initialize(
        self,
        target_device_ids: list[str] | None = None,
    ) -> None:
        """
        Initialize controller.

        Controllers with a delegated API data provider should only be initialized by that data provider.
        """
        if self._initialized:
            return

        # Always subscribe to connection events for reconnection handling
        self._bridge.events.subscribe(EventBrokerTopic.CONNECTION_EVENT, self._base_handle_event)

        # Subscribe to WebSocket resource events if supported by controller
        if self._supported_resource_events:
            self._bridge.events.subscribe(EventBrokerTopic.RAW_RESOURCE_EVENT, self._base_handle_event)

        # Bail now if we depend on another controller for API data.
        if self._api_data_provider:
            self._initialized = True
            self._api_data_unsubscribe = await self._api_data_provider.subcontroller_data_subscribe(
                [self.resource_type], self._refresh
            )
            return

        if target_device_ids is not None:
            self._target_device_ids.update(target_device_ids)
            # If this is a device controller and no device IDs are provided, mark as initialized and skip
            if getattr(self, "_is_device_controller", False) and not self._target_device_ids:
                self._initialized = True
                self._has_no_devices = True
                return

        self._initialized = True

        await self._refresh()

    async def add_target(self, resource_id: str) -> AdcResourceT | None:
        """Add a device ID to the controller's list of targets."""

        self._target_device_ids.add(resource_id)
        self._has_no_devices = False

        await self._refresh(resource_id=resource_id)

        return self._resources.get(resource_id)

    #####################
    # DEVICE MANAGEMENT #
    #####################

    def _device_filter(self, response: list[Resource] | Resource) -> list[Resource] | Resource:
        """
        Filter out unsupported devices from API response.

        Intended to be overridden by child classes.
        """
        return response

    async def _send_command(self, id: str, action: str, msg_body: dict[str, Any] | None = None) -> None:
        """Send command to API."""

        msg_body = msg_body or {}

        if not self.get(id):
            raise UnknownDevice(f"Device {id} not found.")

        await self._bridge.post(
            path=self._resource_url_override or self.resource_type,
            action=action,
            id=id,
            json={"statePollOnly": False, **msg_body},
        )

    async def _refresh(
        self,
        pre_fetched: list[Resource] | None = None,
        resource_id: str | None = None,
        fetch_started: float | None = None,
    ) -> None:
        """
        Initialize controllers using API response data, either fetched here or by another controller.

        Request all devices in the controller's universe (either all available or all specified by
        target_device_ids):

            pre_fetched = None
            resource_id = None

            Any missing resources previously registered by this controller will be unregistered.

        Request a single device:

            pre_fetched = None
            resource_id = <device_id>

            If the device is not found, it will be unregistered. Other devices will be left alone.

        Use resources retrieved by another controller:

            pre_fetched = <list of resources>
            resource_id = None

            Any missing resources previously registered by this controller will be unregistered.

        fetch_started is the time.monotonic() at which the data was requested. A resource that a WebSocket event
        changed after that moment keeps the event's state: the response may predate the event, and applying it
        would put back the state the event just replaced (a door opened mid-request would read closed again).
        """

        log.info("[%s] Refreshing controller...", self.resource_type.name)

        if pre_fetched is not None and resource_id:
            raise NotImplementedError

        if (self._api_data_provider and pre_fetched is None) or (self._requires_target_ids and not self._target_device_ids):
            return

        # initialize() skips a device controller that has no devices; the periodic refresh has to as well. Asking
        # for a device type the system does not have can earn a 423 (image sensors do), every five minutes.
        if pre_fetched is None and not resource_id and self._has_no_devices:
            return

        if pre_fetched is None:
            ids: str | set[str] | None = None

            # Requests for single devices must use the single device format (/devices/locks/12345-098), not the
            # multi-device format (/devices/locks?id[]=12345-098).
            # Read the id without removing it: pop() emptied the set on the first refresh, so every later
            # refresh of a single-target controller (the device catalog, which feeds every device controller)
            # returned at the guard above without a request.
            if resource_id or len(self._target_device_ids) == 1:
                ids = resource_id or next(iter(self._target_device_ids))
            elif self._target_device_ids:
                ids = self._target_device_ids
            else:
                ids = None

            fetch_started = time.monotonic()
            response = await self._bridge.get(self._resource_url_override or self.resource_type, ids)

            response.data = self._device_filter(response.data)

            # Update included resources cache. If this is a full refresh, overwrite existing cache.
            if resource_id:
                for included_item in response.included:
                    self._included_resources.append(included_item)
            else:
                self._included_resources = response.included or []

            # Send included resources to downstream controllers.
            for resource_type, callbacks in self._api_data_receivers.items():
                included_resources = [
                    included_resource
                    for included_resource in self._included_resources
                    if included_resource.type == resource_type
                ]
                if response.included is not None:
                    for callback in callbacks:
                        if iscoroutinefunction(callback):
                            task = asyncio.create_task(callback(included_resources, fetch_started=fetch_started))
                            self._background_tasks.add(task)
                            task.add_done_callback(self._background_tasks.discard)
                        else:
                            callback(included_resources, fetch_started=fetch_started)

            # Return normalized response data for current resource type.
            pre_fetched = [*(response.data if isinstance(response.data, list) else [response.data])]

        # Find and instantiate supported devices.
        discovered_resource_ids = set({})
        for resource in pre_fetched:
            if resource.type != self.resource_type:
                continue
            if self._superseded_by_event(resource.id, fetch_started) or self._keep_local_state(resource):
                # Still present on the account, so it must not be unregistered below.
                discovered_resource_ids.add(resource.id)
                continue
            if await self._register_or_update_resource(resource) is not None:
                discovered_resource_ids.update({resource.id})

        # Unregister devices that failed to be instantiated or (in the case of multi-device endpoints) appeared in
        # a previous API response but not the current one - once they have been missing for several refreshes.
        missing = {resource_id} - discovered_resource_ids if resource_id else self._resources.keys() - discovered_resource_ids

        for found_id in discovered_resource_ids:
            self._missing_refreshes.pop(found_id, None)

        for missing_resource_id in list(missing):
            if missing_resource_id not in self._resources:
                continue

            count = self._missing_refreshes.get(missing_resource_id, 0) + 1

            if count < self._missing_refreshes_before_removal:
                self._missing_refreshes[missing_resource_id] = count
                log.warning(
                    "[%s] %s was missing from Alarm.com's response (%s of %s before it is removed).",
                    self.resource_type.name,
                    missing_resource_id,
                    count,
                    self._missing_refreshes_before_removal,
                )
                continue

            self._missing_refreshes.pop(missing_resource_id, None)
            await self._unregister_resource(missing_resource_id)

    def _superseded_by_event(self, resource_id: str, fetch_started: float | None) -> bool:
        """Whether a WebSocket event changed this resource after the data being applied was requested."""

        if fetch_started is None or resource_id not in self._resources:
            return False

        if self._last_event_at.get(resource_id, float("-inf")) < fetch_started:
            return False

        log.debug(
            "[%s] Keeping event state for %s; the refresh was requested before the event arrived.",
            self.resource_type.name,
            resource_id,
        )
        return True

    def _keep_local_state(self, resource: Resource) -> bool:
        """
        Whether a refresh should leave this already-registered resource as it is.

        Intended to be overridden: the sensor controller keeps a motion sensor it cleared locally, because
        Alarm.com goes on reporting "activated" for up to an hour after the motion stopped.
        """
        return False

    def _request_reconcile(self, reason: str) -> None:
        """Ask the bridge to re-fetch device state shortly, so an assumed or possibly missed state gets checked."""

        if (request := getattr(self._bridge, "request_reconcile", None)) is not None:
            request(reason)

    #############################
    # WEBSOCKET UPDATE HANDLERS #
    #############################

    async def _base_handle_event(self, message: EventBrokerMessage) -> None:
        """Universal event handling for WebSockets messages."""

        # Refresh this controller on its configured WebSocket connection events.
        if isinstance(message, ConnectionEvent) and message.current_state in self._refresh_connection_states:
            try:
                return await self._refresh()
            except NotAuthorized:
                # Some resource types (e.g. imageSensors) return 423 for accounts that don't
                # have that feature. Swallow the error here so one unsupported controller
                # doesn't crash the reconnect refresh for all other controllers.
                log.debug(
                    "[%s] Skipping connection refresh — endpoint not authorized for this account (423).",
                    self.resource_type.name,
                )

        if not isinstance(message, RawResourceEventMessage):
            return None

        # Image sensors use device_id instead of full_device_id.
        adc_resource = self.get(message.ws_message.full_device_id) or self.get(str(message.ws_message.device_id))
        if not adc_resource:
            return None

        # Stamped before anything is applied, so a refresh response processed while this handler awaits below
        # already knows it is older than this event.
        self._last_event_at[adc_resource.id] = time.monotonic()

        # Handle state updates for all controllers that have a state map.
        if (
            self._event_state_map
            and isinstance(message.ws_message, EventWSMessage)
            and message.ws_message.subtype in self._event_state_map
        ):
            adc_resource.api_resource.attributes.update(
                {
                    ATTR_STATE: self._event_state_map[message.ws_message.subtype].value,
                    ATTR_DESIRED_STATE: self._event_state_map[message.ws_message.subtype].value,
                }
            )

        # Send to individual controller for additional changes.
        with contextlib.suppress(NotImplementedError):
            adc_resource = await self._handle_event(adc_resource, message.ws_message)

        # Update registry and send notification to subscribers.
        await self._register_or_update_resource(adc_resource.api_resource)

        return None

    async def _handle_event(self, adc_resource: AdcResourceT, message: BaseWSMessage) -> AdcResourceT:
        """
        Individual controller functions for handling WebSockets messages.

        Takes api_resource and WebSocket message as input. Returns updated api_resource.
        """

        raise NotImplementedError

    ###############################
    # SUB-CONTROLLER REGISTRATION #
    ###############################

    async def subcontroller_data_subscribe(
        self,
        resource_types: list[ResourceType],
        callback: Callable[..., Awaitable | None],
    ) -> Callable:
        """Register controller that depends on this controller for API updates."""

        for resource_type in resource_types:
            self._api_data_receivers.setdefault(resource_type, []).append(callback)

        # log.debug(f"New API data subscriber for {resource_types} to {self.resource_type.name} controller.")

        # Send data if dependent subscribes after fetch.
        if len(self._included_resources) > 0:
            for resource_type in resource_types:
                resources = [
                    included_resource
                    for included_resource in self._included_resources
                    if included_resource.type == resource_type
                ]
                if iscoroutinefunction(callback):
                    task = asyncio.create_task(callback(resources))
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
                else:
                    callback(resources)

        def unsubscribe() -> None:
            """Unregister dependent controller."""
            for resource_type in resource_types:
                self._api_data_receivers[resource_type].remove(callback)

        return unsubscribe

    ##################
    # DEVICE RECORDS #
    ##################

    async def _inject_attributes(self, resource: AdcResourceT) -> AdcResourceT:
        """Inject attributes into resource."""

        # This is a no-op for most controllers, but some (e.g. Thermostats) require it.

        return resource

    async def _register_or_update_resource(self, resource: Resource) -> str | None:
        """Instantiate resource, add to controller's registry, and notify subscribers."""

        try:
            new_adc_resource = self._resource_class(resource)
            new_adc_resource = await self._inject_attributes(new_adc_resource)
        except Exception:
            log.exception(
                "[%s] Failed to instantiate %s, %s. Moving on...",
                self.resource_type.name,
                resource.type,
                resource.id,
            )
            return None

        # Check whether any underlying data has changed. We instantiate first (above) since we only
        # want to notify subscribers if attributes used by this library have changed.
        if ((existing_adc_resource := self.get(resource.id)) is not None) and (
            existing_adc_resource.attributes == new_adc_resource.attributes
        ):
            return resource.id

        try:
            self._has_no_devices = False
            self._resources.update({resource.id: new_adc_resource})
        except Exception:
            log.exception(
                "[%s] Failed to instantiate %s, %s. Moving on...",
                self.resource_type.name,
                resource.type,
                resource.id,
            )
            return None

        if existing_adc_resource:
            log.debug(
                "[%s] Updated %s %s.",
                self.resource_type.name,
                resource.id,
                getattr(new_adc_resource.attributes, "description", ""),
            )
            self._bridge.events.publish(
                ResourceEventMessage(
                    topic=EventBrokerTopic.RESOURCE_UPDATED,
                    id=resource.id,
                    resource=new_adc_resource,
                )
            )
        else:
            log.debug(
                "[%s] Registered %s %s.",
                self.resource_type.name,
                resource.id,
                getattr(new_adc_resource.attributes, "description", ""),
            )
            self._bridge.events.publish(
                ResourceEventMessage(
                    topic=EventBrokerTopic.RESOURCE_ADDED,
                    id=resource.id,
                    resource=new_adc_resource,
                )
            )

        return resource.id

    async def _unregister_resource(self, resource_id: str) -> None:
        """Remove resource from registry and notify subscribers."""

        log.debug("[%s] Unregistering %s...", self.resource_type.name, resource_id)

        resource = self._resources.pop(resource_id, None)

        self._bridge.events.publish(
            ResourceEventMessage(
                topic=EventBrokerTopic.RESOURCE_DELETED,
                id=resource_id,
                resource=resource,
            )
        )

    ####################
    # OBJECT FUNCTIONS #
    ####################

    def get(self, id: str, default: Any = None) -> AdcResourceT | Any | None:
        """Return resource by ID."""
        return self._resources.get(id, default)

    def __getitem__(self, id: str) -> AdcResourceT:
        """Return resource by ID."""
        return self._resources[id]

    def __iter__(self) -> Iterator[AdcResourceT]:
        """Iterate over resources."""
        return iter(self._resources.values())

    def __contains__(self, id: str) -> bool:
        """Return whether resource is present."""
        return id in self._resources

    def __add__(self, other: BaseController) -> list[AdcResource]:
        """Combine resources from two controllers."""

        if not isinstance(other, BaseController):
            raise TypeError("Can only add two BaseController instances together.")

        return list(self._resources.values()) + list(other._resources.values())

    @property
    def resources_pretty(self) -> Group:
        """Return pretty Rich representation of resources in controller."""

        return resources_pretty(self.resource_type.name, list(self._resources.values()))

    @property
    def resources_raw(self) -> Group:
        """Return Rich representation raw JSON for all controller resources."""

        return resources_raw(self.resource_type.name, list(self._resources.values()))

    @property
    def included_raw_str(self) -> Group:
        """Return Rich representation of raw JSON for all controller resources."""

        return resources_raw(f"{self.resource_type.name} Children", list(self._included_resources))
