"""pyalarmdotcomajax - A Python library for interacting with Alarm.com's API."""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import json
import logging
import time
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from types import TracebackType
from typing import TYPE_CHECKING, Any, Literal, TypeVar, overload
from urllib.parse import urlencode

import aiohttp
import humps
from _pyalarmdotcomajax._version import __version__
from _pyalarmdotcomajax.access import DeviceAccessManager
from _pyalarmdotcomajax.const import (
    API_URL_BASE,
    REQUEST_RETRY_LIMIT,
    SUBMIT_RETRY_LIMIT,
    URL_BASE,
    ResponseTypes,
)
from _pyalarmdotcomajax.controllers import (
    AdcControllerT,
    AdcSuccessDocumentMulti,
    AdcSuccessDocumentSingle,
)
from _pyalarmdotcomajax.controllers.auth import AuthenticationController
from _pyalarmdotcomajax.controllers.base import BaseController
from _pyalarmdotcomajax.controllers.cameras import CameraController
from _pyalarmdotcomajax.controllers.device_catalogs import DeviceCatalogController
from _pyalarmdotcomajax.controllers.garage_doors import GarageDoorController
from _pyalarmdotcomajax.controllers.gates import GateController
from _pyalarmdotcomajax.controllers.image_sensors import (
    ImageSensorController,
    ImageSensorImageController,
)
from _pyalarmdotcomajax.controllers.lights import LightController
from _pyalarmdotcomajax.controllers.locks import LockController
from _pyalarmdotcomajax.controllers.partitions import PartitionController
from _pyalarmdotcomajax.controllers.sensors import SensorController
from _pyalarmdotcomajax.controllers.systems import SystemController
from _pyalarmdotcomajax.controllers.thermostats import ThermostatController
from _pyalarmdotcomajax.controllers.trouble_conditions import TroubleConditionController
from _pyalarmdotcomajax.controllers.users import (
    AvailableSystemsController,
)
from _pyalarmdotcomajax.controllers.water_sensors import WaterSensorController
from _pyalarmdotcomajax.controllers.water_valve import WaterValveController
from _pyalarmdotcomajax.events import (
    EventBroker,
    EventBrokerCallbackT,
    EventBrokerMessage,
    EventBrokerTopic,
    ResourceEventMessage,
)
from _pyalarmdotcomajax.exceptions import (
    AlarmdotcomException,
    AuthenticationException,
    AuthenticationFailed,
    MustConfigureMfa,
    NotAuthorized,
    NotInitialized,
    OtpRequired,
    ServiceUnavailable,
    SessionExpired,
    UnexpectedResponse,
    UnknownDevice,
    UnsupportedOperation,
)
from _pyalarmdotcomajax.light_discovery import summarize_light_discovery
from _pyalarmdotcomajax.models import (
    AdcManagedDeviceT,
    AdcMiniSuccessResponse,
    AdcResourceT,
    base,
    camera,
    garage_door,
    gate,
    image_sensor,
    light,
    lock,
    partition,
    sensor,
    system,
    thermostat,
    trouble_condition,
    user,
    water_sensor,
    water_valve,
)
from _pyalarmdotcomajax.models.auth import OtpType
from _pyalarmdotcomajax.models.base import (
    AdcDeviceResource,
    AdcResource,
    BaseManagedDeviceAttributes,
    ResourceType,
)
from _pyalarmdotcomajax.models.history_event import HistoryEvent
from _pyalarmdotcomajax.models.jsonapi import (
    FailureDocument,
    JsonApiBaseElement,
    MetaDocument,
    SuccessDocument,
)
from _pyalarmdotcomajax.websocket.client import (
    ConnectionEvent,
    WebSocketClient,
    WebSocketState,
)
from mashumaro.exceptions import MissingField
from rich.console import Group

if TYPE_CHECKING:
    from _pyalarmdotcomajax.models.system import System

__all__: tuple[str, ...] = (  # noqa: RUF022
    # exceptions
    "AlarmdotcomException",
    "UnsupportedOperation",
    "UnknownDevice",
    "AuthenticationFailed",
    "AuthenticationException",
    "OtpRequired",
    "MustConfigureMfa",
    "SessionExpired",
    "ServiceUnavailable",
    "NotAuthorized",
    "NotInitialized",
    "UnexpectedResponse",
    # models.auth
    "OtpType",
    # websocket
    "WebSocketState",
    "ConnectionEvent",
    # events
    "EventBrokerTopic",
    "EventBrokerMessage",
    "EventBrokerCallbackT",
    "ResourceEventMessage",
    # models
    "AdcResourceT",
    "AdcManagedDeviceT",
    "base",
    "camera",
    "garage_door",
    "gate",
    "image_sensor",
    "light",
    "lock",
    "partition",
    "sensor",
    "system",
    "thermostat",
    "trouble_condition",
    "user",
    "water_sensor",
    "water_valve",
    # controllers
    "AdcControllerT",
)
T = TypeVar("T", bound=JsonApiBaseElement)

log = logging.getLogger(__name__)

# Set while a login is running. Requests made by the login itself must not try to repair the session: the repair
# would log in again from inside the login, and under _login_lock it waits on the lock it already holds.
_LOGIN_IN_PROGRESS: contextvars.ContextVar[bool] = contextvars.ContextVar("adc_login_in_progress", default=False)

# A login that has not finished in this long is abandoned, so a stalled Alarm.com cannot hold _login_lock forever.
LOGIN_REPAIR_TIMEOUT_S = 60

# After a failed session repair, no further login is attempted until this backoff passes; it doubles on each failure.
# A wrong password, a changed password or a locked account would otherwise be retried by every waiting request and
# every poll (several times a minute), which keeps the account locked.
LOGIN_BACKOFF_INITIAL_S = 60
LOGIN_BACKOFF_MAX_S = 30 * 60

# How long a reconcile waits before fetching. Coalesces bursts (several zones changing at once, a reconnect that
# lands with events) into one request, and lets an OpenedClosed pulse play out first.
RECONCILE_DELAY_S = 3.0


FORK_NAME = "ibasebcast"
FORK_REPO = "https://github.com/ibasebcast/pyalarmdotcomajax"

MFA_COOKIE_KEY = "twoFactorAuthenticationId"


class AlarmBridge:
    """Alarm.com bridge."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        mfa_token: str | None = None,
    ) -> None:
        """Initialize alarm bridge."""

        # We allow username and password to be set after initialization so that we can use an instantiated
        # (but not initialized) AlarmBridge to populate the adc cli command list.

        self._initialized = False
        self.device_access = DeviceAccessManager(self)

        # Event Broker
        self.events = EventBroker()

        # Debounced device re-fetch; see request_reconcile().
        self._reconcile_task: asyncio.Task | None = None
        self._reconcile_requested = False

        # Session
        self._websession: aiohttp.ClientSession | None = None
        self.ajax_key: str | None = None

        # Guards concurrent session repair. Without this, each of several concurrent pollers
        # that hit a 403 independently calls login(), and each login() invalidates the ajax_key
        # the previous one just obtained, producing a self-sustaining storm of real logins against
        # Alarm.com (which can trip their account-lockout / notification systems). The generation
        # counter lets a task that queued on the lock discover the session was already repaired by
        # someone else while it waited, and skip its own login.
        self._login_lock = asyncio.Lock()
        self._login_generation = 0
        # Outcome of the latest session repair, and when the next one may be attempted.
        self._last_login_error: BaseException | None = None
        self._login_retry_at = 0.0
        self._login_backoff_s: float = LOGIN_BACKOFF_INITIAL_S

        # Session Controllers
        self._auth_controller = AuthenticationController(
            self, username, password, mfa_token
        )
        self._ws_controller = WebSocketClient(self)

        # Meta Resource Controllers
        self._available_device_catalogs = AvailableSystemsController(self)
        self._systems = SystemController(self)
        self._trouble_conditions = TroubleConditionController(self)

        # Device Resource Controllers
        self._device_catalogs = DeviceCatalogController(self)
        self._cameras = CameraController(self, self._device_catalogs)
        self._garage_doors = GarageDoorController(self, self._device_catalogs)
        self._lights = LightController(self, self._device_catalogs)
        self._gates = GateController(self, self._device_catalogs)
        self._locks = LockController(self, self._device_catalogs)
        self._partitions = PartitionController(self, self._device_catalogs)
        self._sensors = SensorController(self, self._device_catalogs)
        self._thermostats = ThermostatController(self, self._device_catalogs)
        self._water_sensors = WaterSensorController(self, self._device_catalogs)
        # Some catalogs omit valve resources even though system relationships advertise them.
        # Fetch only the discovered valve IDs directly, as for image sensors (#178).
        self._water_valves = WaterValveController(self)

        self._image_sensors = ImageSensorController(self)
        self._image_sensor_images = ImageSensorImageController(self)
        log.debug(
            "IBASEBCAST pyalarmdotcomajax fork loaded, version=%s, repo=%s",
            __version__,
            FORK_REPO,
        )

    async def initialize(self) -> None:
        """Initialize bridge connection, or finish initialization after OTP has been submitted."""

        # TODO: REFRESH IMAGE SENSORS / PROFILE / ETC ON SCHEDULE (DO IN INTEGRATION)
        # TODO: SKYBELL HD

        if self._initialized:
            return

        if not await self.is_logged_in():
            await self.login()

        await self.fetch_full_state()

        self._initialized = True

    async def is_logged_in(self, *, throw: bool = False) -> bool:
        """Check if we are still logged in. Also functions as keep alive signal."""

        try:
            url = f"{URL_BASE[:-1]}{self.auth_controller.keep_alive_url}?"
            f"timestamp={round(datetime.now().timestamp())}"
        except IndexError as err:
            # User has yet to log in.
            if throw:
                raise NotInitialized from err

            return False

        text_rsp = ""

        try:
            async with self.create_request(
                "post",
                url,
                accept_types=ResponseTypes.JSON,
                use_ajax_key=True,
                raise_for_status=True,
                json={},
            ) as rsp:
                text_rsp = await rsp.text()

        except aiohttp.ClientResponseError as err:
            if err.status == 403:
                log.debug("Session expired.")

                if throw:
                    raise SessionExpired from err

                return False

            raise UnexpectedResponse(
                f"Failed to send keep alive signal. Response: {text_rsp}"
            ) from err

        return True

    async def login(self) -> None:
        """Login to alarm.com."""

        token = _LOGIN_IN_PROGRESS.set(True)
        try:
            return await self._auth_controller.login()
        finally:
            _LOGIN_IN_PROGRESS.reset(token)

    async def _repair_session(self, login_generation: int) -> None:
        """
        Log in again after the session expired, once for all concurrent callers.

        login_generation is the generation the caller saw before its request went out. If any login attempt has
        happened since, its outcome stands for this caller too: a success means retry the request, a failure means
        fail without another attempt. A failed attempt also starts a backoff that later callers respect.

        Raises:
            OtpRequired / MustConfigureMfa: Alarm.com wants a one-time code; only reauthentication can fix it.
            AuthenticationFailed: The credentials were rejected (or were, within the backoff).
            ServiceUnavailable: Alarm.com could not be reached or answered unexpectedly.

        """

        async with self._login_lock:
            if login_generation != self._login_generation:
                if self._last_login_error is None:
                    log.debug("Session already repaired by another task; retrying.")
                    return
                raise self._repeat_login_failure()

            if time.monotonic() < self._login_retry_at:
                raise self._repeat_login_failure()

            log.info("Attempting to repair session.")
            token = _LOGIN_IN_PROGRESS.set(True)
            try:
                async with asyncio.timeout(LOGIN_REPAIR_TIMEOUT_S):
                    await self._auth_controller.login()
            except (OtpRequired, MustConfigureMfa) as err:
                self._record_login_failure(err)
                raise
            except AuthenticationException as err:
                self._record_login_failure(err)
                raise AuthenticationFailed("Session repair failed: the login was rejected.") from err
            except (TimeoutError, aiohttp.ClientError, AlarmdotcomException) as err:
                self._record_login_failure(err)
                raise ServiceUnavailable("Session repair failed: Alarm.com could not complete the login.") from err
            finally:
                _LOGIN_IN_PROGRESS.reset(token)
                self._login_generation += 1

            self._last_login_error = None
            self._login_retry_at = 0.0
            self._login_backoff_s = LOGIN_BACKOFF_INITIAL_S

    def _record_login_failure(self, err: BaseException) -> None:
        """Remember a failed repair and start (or lengthen) the backoff before the next one."""

        self._last_login_error = err
        self._login_retry_at = time.monotonic() + self._login_backoff_s
        log.warning(
            "Alarm.com session repair failed (%s). Not logging in again for %s seconds.",
            type(err).__name__,
            round(self._login_backoff_s),
        )
        self._login_backoff_s = min(self._login_backoff_s * 2, LOGIN_BACKOFF_MAX_S)

    def _repeat_login_failure(self) -> AlarmdotcomException:
        """Build the error for a caller that arrives while the latest repair's failure still stands."""

        err = self._last_login_error

        if isinstance(err, (OtpRequired, MustConfigureMfa)):
            return err
        if isinstance(err, AuthenticationException):
            return AuthenticationFailed("A recent session repair was rejected; waiting before trying again.")
        return ServiceUnavailable("A recent session repair failed; waiting before trying again.")

    async def get_activity_history(
        self,
        start_time: datetime,
        end_time: datetime | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> list[HistoryEvent]:
        """
        Fetch activity history events in the given time range.

        Uses an entirely undocumented endpoint (`activity/activityDays`),
        reverse-engineered from the Alarm.com web app's own Activity page
        rather than found in any prior version of this library. Confirmed
        directly from real captured requests, not guessed from other
        endpoints' conventions - see the comments on individual parameters
        below for what's actually been observed.

        Unlike every other resource this library models, history events
        have no persistent state and never arrive over the websocket -
        they have to be actively polled, which is why this lives as a
        plain bridge-level method rather than a BaseController subclass
        (there is no ongoing "controller" of history events to maintain,
        no subscribe-to-live-updates behavior that would apply here).

        Args:
            start_time: earliest event to include (inclusive), aware datetime.
            end_time: latest event to include - omit (None) for "now",
                matching the real web app's own behavior of leaving this
                blank for its default view.
            page: 1-indexed page number - confirmed real parameter, the
                web app increments this to load older activity.
            page_size: confirmed real parameter; the web app itself uses
                100, kept as this method's own default to match.

        Returns:
            Every activity/history-event resource found in the response's
            `included` array - the response's own `data` array (grouped by
            day) is intentionally not modeled here, since nothing about
            the day-grouping itself is needed for any current use case.

        """

        params: dict[str, str] = {
            "debounceTimeMs": "1000",
            "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S.000Z") if end_time else "",
            "page": str(page),
            "pageSize": str(page_size),
            "searchString": "",
            "showOnlyOpenEyeEvents": "false",
        }

        response = await self.get("activity/activityDays", None, params=params)

        return [
            HistoryEvent(api_resource=resource)
            for resource in response.included
            if resource.type == ResourceType.HISTORY_EVENT.value
        ]

    @staticmethod
    def _build_light_discovery_path(light_ids: set[str]) -> str:
        """Build an ID-scoped light request, including for a single device."""
        if not light_ids:
            raise ValueError("At least one light ID is required.")
        return "devices/lights?" + urlencode(
            [("ids[]", device_id) for device_id in sorted(light_ids)]
        )

    async def fetch_full_state(self) -> None:
        """Fetch full state from alarm.com."""

        # 1. Initialize system and device catalog controllers first
        await self._available_device_catalogs.initialize()
        if not self._available_device_catalogs.active_system_id:
            raise AuthenticationFailed("No active system found.")
        await self._systems.initialize()
        await self._device_catalogs.initialize(
            [self._available_device_catalogs.active_system_id]
        )
        await self._partitions.initialize()
        if self._auth_controller.has_trouble_conditions_service:
            await self._trouble_conditions.initialize()

        # 2. Gather device IDs for each device controller type
        device_ids_by_type: dict[type, list[str]] = {}
        for controller in self.resource_controllers:
            if controller.is_device_controller:
                resource_type = controller.resource_type
                # Use the system controller's items for device discovery
                # Within each relationship entry in relationships, we're looking at type in each ResourceIdentifier in data.
                if resource_type and (
                    relationships := self._systems.items[0].api_resource.relationships
                ):
                    for relationship in relationships.values():
                        for resource_identifier in relationship.data_list:
                            if resource_identifier.type == resource_type:
                                device_ids_by_type.setdefault(
                                    type(controller), []
                                ).append(resource_identifier.id)

        log.debug("Discovered device IDs by type: %s", device_ids_by_type)

        # 3. Initialize device controllers with discovered device IDs (or empty list)
        init_tasks = []
        for controller in self.resource_controllers:
            if controller.is_device_controller:
                ids = device_ids_by_type.get(type(controller), [])
                # Most controllers have already been initialized as dependents of the device catalog controller.
                # We're counting on the initialize() method to check if the controller is already initialized.
                # This entire process is to ensure that we don't hit the image sensor endpoint if we don't have
                # any image sensors. Doing so causes a 423 error.
                init_tasks.append(controller.initialize(target_device_ids=ids))
        if init_tasks:
            await asyncio.gather(*init_tasks)

        # Some providers reject an unscoped lights request with HTTP 423.
        # The Alarm.com web portal instead requests lights with explicit ids[].
        # Only use IDs actually advertised by the system/catalog; never guess IDs.
        if not self._lights.items:
            light_ids = set(device_ids_by_type.get(type(self._lights), []))
            light_ids.update(self._lights._target_device_ids)  # noqa: SLF001
            # Some accounts advertise light IDs in catalog relationships.
            for catalog in self._device_catalogs.items:
                for relationship in (catalog.api_resource.relationships or {}).values():
                    light_ids.update(
                        item.id for item in relationship.data_list
                        if item.type == ResourceType.LIGHT
                    )
            light_ids.update(
                item.id for item in self._device_catalogs._included_resources  # noqa: SLF001
                if item.type == ResourceType.LIGHT
            )
            if not light_ids:
                # Some system collection responses omit the lights relationship.
                # Request the active system's detail endpoint explicitly, matching
                # the Alarm.com web portal's light discovery sequence.
                try:
                    system_id = self._available_device_catalogs.active_system_id
                    log.debug(
                        "Light discovery: requesting active system detail for light IDs."
                    )
                    log.debug(
                        "Light discovery probe: requested system is present in loaded systems: %s.",
                        any(system.id == system_id for system in self._systems.items),
                    )
                    system_detail = await self.get(
                        "systems/systems", system_id,
                        light_discovery_system_id=system_id,
                    )
                    system_resources = (
                        system_detail.data
                        if isinstance(system_detail.data, list)
                        else [system_detail.data]
                    )
                    relationship_keys: set[str] = set()
                    light_entry_count = 0
                    for system_resource in system_resources:
                        relationships = system_resource.relationships or {}
                        relationship_keys.update(relationships)
                        lights_relationship = relationships.get("lights")
                        if lights_relationship:
                            entries = lights_relationship.data_list
                            light_entry_count += len(entries)
                            # The named lights relationship defines the device
                            # category. Do not discard its advertised IDs just
                            # because a provider uses a different type label.
                            light_ids.update(
                                item.id for item in entries
                                if isinstance(item.id, str) and item.id.strip()
                            )
                    log.debug(
                        "Light discovery: system detail returned %d light IDs; "
                        "lights relationship present: %s; relationship count: %d; "
                        "lights relationship entries: %d.",
                        len(light_ids),
                        "lights" in relationship_keys,
                        len(relationship_keys),
                        light_entry_count,
                    )
                except Exception as err:
                    log.warning(
                        "Light discovery: active system detail lookup failed (%s).",
                        type(err).__name__,
                    )
            if light_ids:
                try:
                    # Use ids[] even for one light (not /lights/{id}).
                    scoped_path = self._build_light_discovery_path(light_ids)
                    light_response = await self.get(scoped_path, None)
                    light_resources = (
                        light_response.data
                        if isinstance(light_response.data, list)
                        else [light_response.data]
                    )
                    await self._lights._refresh(pre_fetched=light_resources)  # noqa: SLF001
                    log.info("ID-scoped light discovery registered %d lights.", len(self._lights.items))
                except Exception:
                    log.exception("ID-scoped light discovery failed.")
            else:
                # Preserve unscoped discovery for accounts where it works.
                # Some providers return HTTP 423, which is nonfatal.
                try:
                    response = await self.get(ResourceType.LIGHT, None)
                    resources = response.data if isinstance(response.data, list) else [response.data]
                    await self._lights._refresh(pre_fetched=resources)  # noqa: SLF001
                    log.info("Unscoped light discovery registered %d lights.", len(self._lights.items))
                except Exception:
                    log.debug("Unscoped light discovery unavailable; no known light IDs for scoped retry.")

    async def refresh_all_resources(self) -> None:
        """
        Force a re-fetch and re-publish of state for every already-initialized resource controller.

        fetch_full_state() (and the controller.initialize() calls it makes) is a one-time
        setup path: each controller's initialize() returns immediately if it has already run
        once, so calling fetch_full_state() again - e.g. from a periodic safety-net poll meant
        to catch state missed by a dropped WebSocket event - is a silent no-op. It does not
        raise, log a warning, or refresh anything.

        This method instead calls each controller's _refresh() directly, the same mechanism
        already used to catch up state when the WebSocket reconnects (see
        BaseController._base_handle_event). Unlike initialize(), _refresh() has no one-time
        guard and safely re-fetches and re-publishes RESOURCE_UPDATED events every time it's
        called.
        """

        refresh_tasks = [
            controller._refresh()  # noqa: SLF001
            for controller in self.resource_controllers
            if controller.initialized
        ]

        if not refresh_tasks:
            return

        results = await asyncio.gather(*refresh_tasks, return_exceptions=True)

        # One controller failing must not stop the others, but an authentication failure has to reach the
        # caller: it is how the hub learns that the session cannot be repaired and reauthentication is needed.
        # NotAuthorized is not one. It is Alarm.com's 406/423 for an endpoint this account cannot use (a feature
        # missing from the plan, a device type disabled), and the session is fine. Passing it up made the hub log in
        # again every few minutes for as long as that endpoint kept refusing.
        for result in results:
            if isinstance(result, AuthenticationException) and not isinstance(result, NotAuthorized):
                raise result
            if isinstance(result, NotAuthorized):
                log.debug("A controller refresh was refused by Alarm.com (not a login problem): %s", result)
            elif isinstance(result, Exception):
                log.debug("A controller refresh failed: %r", result)


    def request_reconcile(self, reason: str, delay_s: float = RECONCILE_DELAY_S) -> None:
        """
        Re-fetch device state shortly, coalescing a burst of requests into one fetch.

        WebSocket events are deltas with no replay, so any event that arrives while the socket is between
        connections is lost, and an OpenedClosed event only implies that the sensor ended closed. Each of those
        moments asks for a reconcile: one device-catalog request that carries every sensor, partition, lock,
        etc., applied under BaseController's guard so it cannot undo an event that arrived after it was sent.
        """

        self._reconcile_requested = True

        if self._reconcile_task is not None and not self._reconcile_task.done():
            # The running task re-checks the flag after its fetch, so a request made while that fetch is in
            # flight still gets a fetch that starts after it.
            return

        self._reconcile_task = asyncio.create_task(self._reconcile(reason, delay_s), name="Alarm.com reconcile")

    async def _reconcile(self, reason: str, delay_s: float) -> None:
        """Run requested reconciles until no new request arrived during the last fetch."""

        while self._reconcile_requested:
            await asyncio.sleep(delay_s)
            self._reconcile_requested = False

            if not self._initialized or not self._device_catalogs.initialized:
                return

            log.debug("Reconciling device state (%s).", reason)

            try:
                await self._device_catalogs._refresh()  # noqa: SLF001
            except Exception:
                # The periodic full refresh is the backstop; a failed reconcile must not take anything down.
                log.debug("Reconcile failed (%s).", reason, exc_info=True)
                return

    async def start_event_monitoring(
        self, ws_status_callback: EventBrokerCallbackT | None = None
    ) -> Callable | None:
        """Start real-time event monitoring."""

        await self._ws_controller.initialize()

        if ws_status_callback:
            return self.events.subscribe(
                EventBrokerTopic.CONNECTION_EVENT, ws_status_callback
            )

        return None

    def subscribe(
        self,
        callback: EventBrokerCallbackT,
        ids: list[str] | str | None = None,
    ) -> Callable[[], None]:
        """
        Subscribe to status changes for all resource controllers.

        Returns:
            function to unsubscribe.

        """
        return self.events.subscribe(
            [
                EventBrokerTopic.RESOURCE_ADDED,
                EventBrokerTopic.RESOURCE_DELETED,
                EventBrokerTopic.RESOURCE_UPDATED,
                EventBrokerTopic.CONNECTION_EVENT,
            ],
            callback,
            ids,
        )

    ###################
    # GET CONTROLLERS #
    ###################

    @property
    def lights(self) -> LightController:
        """Get the lights controller."""

        return self._lights

    @property
    def cameras(self) -> CameraController:
        """Get the cameras controller."""
        return self._cameras

    @property
    def garage_doors(self) -> GarageDoorController:
        """Get the garage doors controller."""
        return self._garage_doors

    @property
    def gates(self) -> GateController:
        """Get the gates controller."""
        return self._gates

    @property
    def image_sensors(self) -> ImageSensorController:
        """Get the image sensors controller."""
        return self._image_sensors

    @property
    def image_sensor_images(self) -> ImageSensorImageController:
        """Get the image sensor images controller."""
        return self._image_sensor_images

    @property
    def locks(self) -> LockController:
        """Get the locks controller."""
        return self._locks

    @property
    def partitions(self) -> PartitionController:
        """Get the partitions controller."""
        return self._partitions

    @property
    def sensors(self) -> SensorController:
        """Get the sensors controller."""
        return self._sensors

    @property
    def systems(self) -> SystemController:
        """Get the system controller."""
        return self._systems

    @property
    def thermostats(self) -> ThermostatController:
        """Get the thermostats controller."""
        return self._thermostats

    @property
    def trouble_conditions(self) -> TroubleConditionController:
        """Get the trouble conditions controller."""
        return self._trouble_conditions

    @property
    def water_sensors(self) -> WaterSensorController:
        """Get the water sensors controller."""
        return self._water_sensors

    @property
    def water_valves(self) -> WaterValveController:
        """Get the water valves controller."""
        return self._water_valves

    @property
    def auth_controller(self) -> AuthenticationController:
        """Get the authentication controller."""
        return self._auth_controller

    @property
    def ws_controller(self) -> WebSocketClient:
        """Get the websocket controller."""
        return self._ws_controller

    @property
    def device_catalogs(self) -> DeviceCatalogController:
        """Get the device catalogs controller."""
        return self._device_catalogs

    @property
    def resource_controllers(self) -> list[BaseController]:
        """Get all resource controllers."""

        # Build and return list of resource controllers by searching self for all attributes that inherit from
        # BaseController
        return [
            controller
            for controller in self.__dict__.values()
            if isinstance(controller, BaseController)
        ]

    def get_controller(self, resource_id: str) -> BaseController:
        """Get the resource controller for a given resource."""

        for controller in self.resource_controllers:
            if resource_id in controller:
                return controller

        raise UnknownDevice(f"Couldn't find controller for: {resource_id}")

    ###################################
    ## PROPERTIES & RESOURCE FINDERS ##
    ###################################

    @property
    def initialized(self) -> bool:
        """Return whether bridge is initialized."""

        return self._initialized

    @property
    def active_system(self) -> System:
        """Get the active system."""

        if not self._available_device_catalogs.active_system_id:
            raise AuthenticationFailed("No active system found.")

        return self._systems[self._available_device_catalogs.active_system_id]

    @property
    def resources(self) -> dict[str, AdcResource]:
        """Get ADC resources across all controllers."""

        return {
            resource.id: resource
            for controller in self.resource_controllers
            for resource in controller.items
            if isinstance(resource, AdcResource)
        }

    @property
    def managed_devices(
        self,
    ) -> dict[str, AdcDeviceResource[BaseManagedDeviceAttributes]]:
        """Get ADC resources across all controllers."""

        return {
            resource.id: resource
            for controller in self.resource_controllers
            for resource in controller.items
            if isinstance(resource, AdcDeviceResource)
            and isinstance(resource.attributes, BaseManagedDeviceAttributes)
        }

    ##########################################
    # REQUEST MANAGEMENT / CONTEXT FUNCTIONS #
    ##########################################

    async def __aenter__(self) -> AlarmBridge:
        """Return Context manager."""

        await self.initialize()

        await self.start_event_monitoring()

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager."""

        await self.close()

    async def close(self) -> None:
        """Close connection and cleanup."""

        self._ws_controller.stop()

        if self._reconcile_task is not None and not self._reconcile_task.done():
            self._reconcile_task.cancel()
        self._reconcile_task = None

        if self._websession:
            await self._websession.close()
        self._websession = None
        self._initialized = False
        log.info("Connection to alarm.com closed.")

    #
    # REQUEST FUNCTIONS
    #

    def build_request_headers(
        self,
        accept_types: ResponseTypes | None = ResponseTypes.JSONAPI,
        *,
        use_ajax_key: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Get session and build headers for request."""

        if "headers" not in kwargs:
            kwargs["headers"] = {}

        kwargs["headers"].update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                ),
                "Referrer": "https://www.alarm.com/web/system/home",
                "Connection": "keep-alive",
            }
        )

        if accept_types is not None:
            kwargs["headers"].update(accept_types.value)

        if use_ajax_key and self.ajax_key:
            kwargs["headers"].update({"Ajaxrequestuniquekey": self.ajax_key})

        return kwargs

    @contextlib.asynccontextmanager
    async def create_request(
        self,
        method: str,
        url: str,
        accept_types: ResponseTypes = ResponseTypes.JSONAPI,
        *,
        use_ajax_key: bool = True,
        **kwargs: Any,
    ) -> AsyncIterator[aiohttp.ClientResponse]:
        """
        Make a request to the Alarm.com API.

        Returns a generator with aiohttp ClientResponse.
        """

        if self._websession is None:
            log.debug("Creating new websession.")
            self._websession = aiohttp.ClientSession()

        if self._auth_controller.mfa_cookie:
            kwargs.setdefault("cookies", {}).update(
                {MFA_COOKIE_KEY: self._auth_controller.mfa_cookie}
            )

        kwargs = self.build_request_headers(
            accept_types=accept_types, use_ajax_key=use_ajax_key, **kwargs
        )

        async with self._websession.request(method, url, **kwargs) as resp:
            # Update anti-forgery cookie.

            # AFG cookie is not always used. This seems to depend on the specific Alarm.com vendor, so a missing
            # AFG key should not cause a failure.
            # Ref: https://www.alarm.com/web/system/assets/addon-tree-output/@adc/ajax/services/adc-ajax.js
            # When used, AFG is not always present in the response. Prior value should carry over until a new value
            # appears.
            #
            # As with the MFA cookie above, aiohttp follows redirects by default and resp.cookies only
            # exposes the Set-Cookie headers of the *last* response in the chain. Fall back to the session
            # cookie jar when afg is not on this response, otherwise a stale ajax_key can be carried over
            # and rejected by the server as "Invalid Anti Forgery" (403).

            new_afg: str | None = None
            if afg := resp.cookies.get("afg"):
                new_afg = afg.value
            elif self._websession is not None:
                for jar_cookie in self._websession.cookie_jar:
                    if jar_cookie.key == "afg" and jar_cookie.value:
                        new_afg = jar_cookie.value
                        break

            if new_afg and new_afg != self.ajax_key:
                self.ajax_key = new_afg

            # Update MFA cookie.
            # We need to store the MFA cookie locally in order to reauthenticate after a session timeout without
            # having to reprompt for an OTP.
            #
            # Alarm.com sets the twoFactorAuthenticationId cookie on the verifyTwoFactorCode /
            # trustTwoFactorDevice responses, but it is not always present on the final
            # ClientResponse: aiohttp follows redirects by default, and resp.cookies only exposes
            # the Set-Cookie headers of the *last* response in the chain. The session cookie jar,
            # however, accumulates cookies from every hop, so fall back to it when the cookie is
            # not on this response. Without this, OTP verification silently fails to produce a
            # token and login is rejected with "Could not find MFA cookie".

            new_mfa_cookie: str | None = None
            if resp_mfa_cookie := resp.cookies.get(MFA_COOKIE_KEY):
                new_mfa_cookie = resp_mfa_cookie.value
            elif self._websession is not None:
                for jar_cookie in self._websession.cookie_jar:
                    if jar_cookie.key == MFA_COOKIE_KEY and jar_cookie.value:
                        new_mfa_cookie = jar_cookie.value
                        break

            if new_mfa_cookie and new_mfa_cookie != self._auth_controller.mfa_cookie:
                log.debug("Got new token from MFA cookie.")
                self._auth_controller.mfa_cookie = new_mfa_cookie

            # Never log HTTP headers, bodies, cookies, OTPs, or response tokens.
            # Even DEBUG logs are routinely attached to public issue reports.
            log.debug("Alarm.com HTTP %s completed with status %s",
                      resp.request_info.method, resp.status)

            yield resp

    @contextlib.asynccontextmanager
    async def ws_connect(
        self,
        url: str,
        **kwargs: Any,
    ) -> AsyncIterator[aiohttp.ClientWebSocketResponse]:
        """
        Establish a WebSocket connection with Alarm.com.

        Returns a generator with aiohttp ClientWebSocketResponse.
        """
        if self._websession is None:
            raise NotInitialized(
                "Cannot initiate WebSocket connection without an existing session."
            )

        # Don't generate/use GET/POST request headers. WebSocket connection uses token in place of cookies, etc.

        async with self._websession.ws_connect(url, **kwargs) as res:
            yield res

    @overload
    async def request(
        self,
        method: str,
        url: str,
        accept_types: ResponseTypes,
        success_response_class: type[T],
        **kwargs: Any,
    ) -> T: ...

    @overload
    async def request(
        self,
        method: str,
        url: str,
        accept_types: ResponseTypes,
        success_response_class: type[SuccessDocument] = SuccessDocument,
        **kwargs: Any,
    ) -> SuccessDocument: ...

    async def request(
        self,
        method: str,
        url: str,
        accept_types: ResponseTypes = ResponseTypes.JSONAPI,
        success_response_class: type[T] | type[SuccessDocument] = SuccessDocument,
        *,
        allow_login_repair: bool = True,
        light_discovery_system_id: str | None = None,
        **kwargs: Any,
    ) -> T | SuccessDocument:
        """Make request to the api and return response data."""

        # Alarm.com's implementation violates the JSON:API spec by sometimes returning a modified error response
        # body with a non-200 response code.
        # This response still contains an "errors" object and should validate as a FailureDocument.

        # Snapshot the login generation before the request goes out. If this request later hits an
        # AuthenticationFailed, we compare against the current generation to detect whether another
        # concurrent task has already repaired the session for us.
        login_generation = self._login_generation

        log.info(
            "Requesting %s expecting %s as %s",
            method.upper(),
            accept_types,
            success_response_class.__name__,
        )

        try:
            async with self.create_request(
                method, url, accept_types, use_ajax_key=True, **kwargs
            ) as raw_resp:
                # Color PUTs can confirm with 204 and no document. Errors still
                # follow the normal status/schema checks and session-repair path.
                if method.lower() == "put" and raw_resp.status == 204:
                    return success_response_class.from_dict({"data": None})

                # Load the response as JSON:API object.

                response: FailureDocument | JsonApiBaseElement | MetaDocument | None = (
                    None
                )

                try:
                    response_text = await raw_resp.text()
                    response = success_response_class.from_json(response_text)
                except json.JSONDecodeError:
                    # Triggered when the response is not valid JSON.
                    raise UnexpectedResponse("Response was not valid JSON.") from None
                except (ValueError, MissingField):
                    # Triggered when discriminator resolution fails or if field is missing in response.
                    pass

                if isinstance(response, success_response_class):
                    if light_discovery_system_id is not None and log.isEnabledFor(logging.DEBUG):
                        try:
                            summary = summarize_light_discovery(
                                json.loads(response_text), response.data, light_discovery_system_id,
                            )
                            log.debug("Light discovery probe: %s", summary)
                        except Exception as probe_error:
                            # A diagnostic must never break discovery or log a payload-bearing exception.
                            log.debug("Light discovery probe unavailable (%s).", type(probe_error).__name__)
                    return response

                # JsonAPI and AdcMini failure responses evaluate to the standard JSON:API FailureDocument.
                try:
                    response = FailureDocument.from_json(await raw_resp.text())
                except (ValueError, MissingField):
                    log.warning("Failed to parse response as FailureDocument.")
                    raise UnexpectedResponse(
                        "Response did not match requested schema definition."
                    ) from None

                # "Successful" FailureDocument requests always return a 200 response code. Non-200 responses
                # indicate server failure.
                # "Successful" AdcMiniResponses requests return non-200 responses for "successful" failures like an
                # incorrect OTP code.

                if hasattr(response, "errors") and isinstance(
                    response, FailureDocument
                ):
                    # Retrieve errors from errors dict object.
                    error_codes = [
                        int(error.code)
                        for error in response.errors
                        if error.code is not None
                    ]

                    # 406: Not Authorized For Ember, 423: Processing Error
                    if any(x in error_codes for x in [406, 423]):
                        log.info(
                            "Got a processing error. This may be caused by missing permissions, being on an "
                            "Alarm.com plan without support for a particular device type, or having a "
                            "device type disabled for this system."
                        )
                        raise NotAuthorized(
                            f"Method: {method}\nStatus Codes: "
                            f"{error_codes}"
                        )

                    # 401: Logged Out, 403: Invalid Anti Forgery
                    if any(x in [401, 403] for x in error_codes):
                        raise AuthenticationFailed(
                            f"Method: {method}\nStatus Codes: "
                            f"{error_codes}",
                            can_autocorrect=True,
                        )

                    # 409: Two Factor Authentication Required
                    if 409 in error_codes:
                        raise AuthenticationFailed(
                            f"Two factor authentication required.\nMethod: {method}\nStatus Codes: "
                            f"{error_codes}"
                        )

                    # 422: Wrong Two Factor Authentication Code
                    if 422 in error_codes:
                        raise AuthenticationFailed(
                            f"Method: {method}\nStatus Codes: "
                            f"{error_codes}"
                        )

                    raise UnexpectedResponse(
                        f"Method: {method}\nStatus Codes: "
                        f"{error_codes}"
                    )

                raw_resp.raise_for_status()

                # Bad things have happened if we reach this point.
                raise UnexpectedResponse

        except AuthenticationFailed as err:
            if not (err.can_autocorrect and allow_login_repair) or _LOGIN_IN_PROGRESS.get():
                raise

            await self._repair_session(login_generation)

        # Outside the except block, so an error on the retry keeps its own type instead of being reported as an
        # authentication failure, and the retry asks for the same response type as the original request.
        return await self.request(
            method,
            url,
            accept_types,
            success_response_class=success_response_class,
            allow_login_repair=False,
            light_discovery_system_id=light_discovery_system_id,
            **kwargs,
        )

    def _generate_request_url(
        self, path: ResourceType | str, id: str | set[str] | None
    ) -> str:
        """
        Generate endpoint URL for request.

        When path is a ResourceType, the URL is generated based on the resource type.
        When path is str, the path is appended to the end of the API base URL.
        """

        # Format path for appropriate resource type & pluralize.
        if isinstance(path, ResourceType):
            path = humps.camelize(path.value) + "s"
        else:
            path.rstrip("/")

        if isinstance(id, set) and len(id) == 1:
            id = id.pop()

        # Format path for single/multi/all.
        if isinstance(id, str):
            # Set path for single resource.
            path += f"/{id}"

        elif isinstance(id, set):
            # Explode IDs if id is a list.
            path += "?" + "&".join([f"ids[]={n}" for n in id])

        return f"{API_URL_BASE}{path}"

    @overload
    async def get(
        self,
        path: ResourceType | str,
        id: str,
        *,
        mini_response: Literal[False] = ...,
        **kwargs: Any,
    ) -> AdcSuccessDocumentSingle: ...

    @overload
    async def get(
        self,
        path: ResourceType | str,
        id: set[str] | None,
        *,
        mini_response: Literal[False] = ...,
        **kwargs: Any,
    ) -> AdcSuccessDocumentMulti: ...

    @overload
    async def get(
        self,
        path: str,
        id: str | None,
        *,
        mini_response: Literal[True],
        **kwargs: Any,
    ) -> AdcMiniSuccessResponse: ...

    async def get(
        self,
        path: ResourceType | str,
        id: str | set[str] | None,
        *,
        mini_response: bool = False,
        **kwargs: Any,
    ) -> AdcSuccessDocumentSingle | AdcSuccessDocumentMulti | AdcMiniSuccessResponse:
        """
            Get resources from the server.

        Args:
            id:             the id(s) of the resource(s) to get.
                            If str, get one resource.
                            If set, get specified.
                            If None, get all.
                            requests for single devices must use the single device format
                            (/devices/locks/12345-098), not the multi-device format
                            (/devices/locks?id[]=12345-098).
            path:           the path of the resource to get.
                            If ResourceType, build path based on resource type.
                            If str, use as is in place of ResourceType-generated path.
            mini_response:  whether the endpoint returns a JSON:API compliant response
                            or an Alarm.com "mini" response.
            kwargs:         additional arguments to pass to the request.

        Returns:
            AdcSuccessDocumentMulti: the response from the server.

        """

        path = self._generate_request_url(path, id)

        retries = 0
        while True:
            try:
                return await self.request(
                    method="get",
                    url=path,
                    accept_types=ResponseTypes.JSON
                    if mini_response
                    else ResponseTypes.JSONAPI,
                    success_response_class=AdcMiniSuccessResponse
                    if mini_response
                    else (
                        AdcSuccessDocumentSingle
                        if isinstance(id, str)
                        else AdcSuccessDocumentMulti
                    ),
                    **kwargs,
                )

            except (TimeoutError, aiohttp.ClientResponseError, aiohttp.ClientConnectionError) as e:
                if retries == REQUEST_RETRY_LIMIT:
                    raise ServiceUnavailable from e
                retries += 1
                continue

    async def post(
        self,
        path: ResourceType | str,
        id: str | set[str] | None,
        action: str | None,
        *,
        mini_response: bool = False,
        **kwargs: Any,
    ) -> AdcSuccessDocumentSingle | AdcMiniSuccessResponse:
        """
        POST to server and return mashumaro deserialized AdcSuccessDocumentSingle or AdcMiniResponse.

        Convenience function that builds URLs based on resource type, ID, action, etc.
        """

        path = self._generate_request_url(path, id) + (f"/{action}" if action else "/")

        retries = 0
        while True:
            try:
                return await self.request(
                    method="post",
                    url=path,
                    accept_types=ResponseTypes.JSON
                    if mini_response
                    else ResponseTypes.JSONAPI,
                    success_response_class=AdcMiniSuccessResponse
                    if mini_response
                    else AdcSuccessDocumentSingle,
                    **kwargs,
                )

            except (TimeoutError, aiohttp.ClientResponseError) as e:
                if retries == SUBMIT_RETRY_LIMIT:
                    raise ServiceUnavailable from e
                retries += 1
                continue

    ############################
    ## RESOURCE PRETTY OUTPUT ##
    ############################

    @property
    def resources_pretty(self) -> Group:
        """Return pretty representation of resources in AlarmBridge."""

        return Group(
            *[
                x.resources_pretty
                for x in sorted(
                    self.resource_controllers, key=lambda x: x.__class__.__name__
                )
            ]
        )

    @property
    def resources_raw(self) -> Group:
        """Return raw JSON for all bridge resources."""

        return Group(
            *[
                x.resources_raw
                for x in sorted(
                    self.resource_controllers, key=lambda x: x.__class__.__name__
                )
            ]
        )
