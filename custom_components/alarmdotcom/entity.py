"""Alarm.com base device."""

from __future__ import annotations

import logging
from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, TypeVar

import pyalarmdotcomajax as pyadc
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.entity import Entity, EntityDescription

# from pyalarmdotcomajax import AdcManagedDeviceT
from .const import DOMAIN
from .util import slug_to_title

if TYPE_CHECKING:
    from .hub import AlarmHub

log = logging.getLogger(__name__)

AdcManagedDeviceT = TypeVar("AdcManagedDeviceT", bound=pyadc.AdcDeviceResource)
AdcControllerT = TypeVar("AdcControllerT", bound=pyadc.BaseController)


@callback
def unique_id_fn(device_id: str, entity_name: str | None) -> str:
    """Return a unique ID."""

    return f"{device_id}_{entity_name}" if entity_name else device_id


@callback
def entity_name_fn(
    hub: AlarmHub, resource_id: str, entity_suffix: str | None
) -> str | None:
    """Return device name."""

    resource = hub.api.managed_devices[resource_id]

    if entity_suffix:
        return (f"{resource.name} {slug_to_title(entity_suffix)}").title()

    return None


@callback
def available_fn(hub: AlarmHub, resource_id: str) -> bool:
    """Check if device is available."""

    resource = hub.api.managed_devices[resource_id]

    return (
        hub.available
        and not resource.attributes.loading
        and (
            not hasattr(resource.attributes, "state")
            or not isinstance(resource.attributes.state, Enum)
            or resource.attributes.state.name != "UNKNOWN"
        )
    )


@callback
def device_info_fn(
    hub: AlarmHub, resource_id: str, entity_name: str | None
) -> DeviceInfo:
    """Return device information."""

    resource = hub.api.managed_devices[resource_id]

    # If not primary entity for device.
    if entity_name:
        return DeviceInfo(identifiers={(DOMAIN, resource.id)})

    # If primary entity for device.
    if partition_id := hub.api.partitions.get_device_partition(resource_id):
        via_device_id: str | None = partition_id
    else:
        via_device_id = getattr(resource, "system_id", None)

    device_info = DeviceInfo(identifiers={(DOMAIN, resource_id)}, name=resource.name)

    if resource.attributes.mac_address not in (None, ""):
        device_info["connections"] = {
            (CONNECTION_NETWORK_MAC, resource.attributes.mac_address)
        }
    else:
        device_info["connections"] = set()
    if resource.attributes.manufacturer is not None:
        device_info["manufacturer"] = resource.attributes.manufacturer
    if resource.attributes.device_model is not None:
        device_info["model"] = resource.attributes.device_model
    if via_device_id:
        device_info["via_device"] = (DOMAIN, via_device_id)

    return device_info


@dataclass(frozen=True, kw_only=True)
class AdcEntityDescription(
    EntityDescription,
    Generic[AdcManagedDeviceT, AdcControllerT],
):
    """Base Alarm.com entity description."""

    # Mandatory Constants
    key: str
    """Must match name of device controller in pyalarmdotcomajax's AlarmBridge."""

    # Mandatory Functions
    controller_fn: Callable[[AlarmHub, str], AdcControllerT]
    """Return device controller. Takes hub and resource ID as arguments."""
    supported_fn: Callable[[AlarmHub, str], bool] = lambda hub, resource_id: True
    """Determine if device provides relevant data for this entity."""

    # Optional Constants
    has_entity_name: bool = True
    """Has entity name defaults to true."""
    should_poll: bool = False
    """Whether entity needs to do regular checks on state."""

    # Optional Functions
    available_fn: Callable[[AlarmHub, str], bool] = available_fn
    """Determine if entity is available, default is if Alarm.com connection is working. Takes hub and resource ID as arguments."""
    extra_attrib_fn: Callable[[pyadc.AdcDeviceResource], dict[str, Any]] = (
        lambda device: {}
    )
    """Provide extra attributes for entity. Takes device as argument."""
    unique_id_fn: Callable[[str, str | None], str] = unique_id_fn
    """Provide a unique ID based on hub and obj_id. Takes resource ID and entity suffix as arguments."""
    device_info_fn: Callable[[AlarmHub, str, str | None], DeviceInfo] = (
        device_info_fn  # Hub, Resource ID, Device Key
    )
    """Provide device info object based on hub and obj_id."""
    entity_name_fn: Callable[[AlarmHub, str, str | None], str | None] = entity_name_fn
    """Provide a name for the entity."""


class AdcEntity(Entity, Generic[AdcManagedDeviceT, AdcControllerT]):
    """Base Alarm.com entity."""

    entity_description: AdcEntityDescription[AdcManagedDeviceT, AdcControllerT]
    controller: AdcControllerT

    def __init__(
        self,
        hub: AlarmHub,
        resource_id: str,
        description: AdcEntityDescription[AdcManagedDeviceT, AdcControllerT],
    ) -> None:
        """Initialize class."""

        self.resource_id = resource_id
        self.hub = hub
        self.entity_description = description

        self.controller = description.controller_fn(hub, resource_id)

        self._attr_should_poll = description.should_poll
        self._attr_available = description.available_fn(hub, resource_id)
        self._attr_extra_state_attributes = description.extra_attrib_fn(
            hub.api.managed_devices[resource_id]
        )

        entity_name = description.name if isinstance(description.name, str) else None

        self._attr_device_info = description.device_info_fn(
            hub, resource_id, entity_name
        )
        self._attr_unique_id = description.unique_id_fn(resource_id, entity_name)
        self._attr_name = description.entity_name_fn(hub, resource_id, entity_name)

        self.initiate_state()

    @callback
    @abstractmethod
    def update_state(self, message: pyadc.EventBrokerMessage | None = None) -> None:
        """Update entity state."""

        raise NotImplementedError

    @callback
    def initiate_state(self) -> None:
        """
        Initiate entity state.

        Perform additional actions setting up platform entity child class state.
        Defaults to using update_state to set initial state.
        """

        # self.entity_description.name sometimes returns as typing.UndefinedType.
        log.debug(
            "Initiating state for %s",
            f"{self.hub.api.managed_devices[self.resource_id].name} - {self.entity_description.name}"
            if isinstance(self.entity_description.name, str)
            else self.hub.api.managed_devices[self.resource_id].name,
        )

        self.update_state(
            pyadc.ResourceEventMessage(
                topic=pyadc.EventBrokerTopic.RESOURCE_ADDED, id=self.resource_id
            )
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        # Subscribe to updates for the device.
        self.async_on_remove(
            self.hub.api.subscribe(self.event_handler, self.resource_id)
        )

    async def remove(self) -> None:
        """Remove entity from Home Assistant."""

        if self.registry_entry:
            er.async_get(self.hass).async_remove(self.entity_id)
        else:
            await self.async_remove(force_remove=True)

    @callback
    def event_handler(self, message: pyadc.EventBrokerMessage) -> None:
        """Handle event message."""

        if message.topic in [
            pyadc.EventBrokerTopic.RESOURCE_ADDED,
            pyadc.EventBrokerTopic.RESOURCE_UPDATED,
            pyadc.EventBrokerTopic.CONNECTION_EVENT,
        ]:
            self._attr_available = self.entity_description.available_fn(
                self.hub, self.resource_id
            )

            if message.topic != pyadc.EventBrokerTopic.CONNECTION_EVENT:
                self.update_state(message)

            self.async_write_ha_state()
        elif message.topic == pyadc.EventBrokerTopic.RESOURCE_DELETED:
            self.hass.async_create_task(self.remove())
