"""Alarmdotcom implementation of an HA button."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from inspect import isawaitable
from typing import TYPE_CHECKING, Any, Generic

import _pyalarmdotcomajax as pyadc
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DEBUG_REQ_EVENT, DOMAIN
from .entity import (
    AdcControllerT,
    AdcEntity,
    AdcEntityDescription,
    AdcManagedDeviceT,
)
from .util import cleanup_orphaned_entities_and_devices

if TYPE_CHECKING:
    from .hub import AlarmHub

# Entities are updated via push (websocket events), not per-entity polling -
# PARALLEL_UPDATES has no effect on update frequency here, but setting it
# to 0 is still the correct, explicit signal for a push-based integration.
PARALLEL_UPDATES = 0

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the button platform."""

    hub: AlarmHub = config_entry.runtime_data.hub

    entities: list[ButtonEntity] = []
    managed_devices = dict(hub.api.managed_devices)

    for entity_description in ENTITY_DESCRIPTIONS:
        entities.extend(
            AdcButtonEntity(
                hub=hub, resource_id=device.id, description=entity_description
            )
            for device in managed_devices.values()
            if entity_description.supported_fn(hub, device.id)
        )

    active_system = hub.api.active_system
    entities.extend(
        [
            AdcSystemButtonEntity(
                hub=hub,
                resource_id=active_system.id,
                key="stop_alarms",
                name="Stop Alarms",
                icon="mdi:alarm-off",
                press_fn=system_stop_alarms_press_fn,
            ),
            AdcSystemButtonEntity(
                hub=hub,
                resource_id=active_system.id,
                key="clear_alarms_in_memory",
                name="Clear Alarms In Memory",
                icon="mdi:alarm-light-off",
                press_fn=system_clear_alarms_in_memory_press_fn,
            ),
        ]
    )

    async_add_entities(entities)

    current_entity_ids = {entity.entity_id for entity in entities}
    current_unique_ids = {
        uid for uid in (entity.unique_id for entity in entities) if uid is not None
    }
    await cleanup_orphaned_entities_and_devices(
        hass, config_entry, current_entity_ids, current_unique_ids, "button"
    )


@dataclass(frozen=True, kw_only=True)
class AdcButtonDescription(
    Generic[AdcManagedDeviceT, AdcControllerT],
    AdcEntityDescription[AdcManagedDeviceT, AdcControllerT],
    ButtonEntityDescription,
):
    """Describes a button entity."""

    press_fn: Callable[[AlarmHub, str], Awaitable[Any] | Any]


def _device_exists_in_registry(hub: AlarmHub, resource_id: str) -> bool:
    """Check if a device with the given ID exists in the device registry."""
    device_registry = dr.async_get(hub.hass)
    # Scoped lookup rather than a scan of device_registry.devices, whose mapping
    # interface is deprecated and stops working in HA Core 2027.9.
    return any(
        (DOMAIN, resource_id) in device.identifiers
        for device in dr.async_entries_for_config_entry(
            device_registry, hub.config_entry.entry_id
        )
    )


async def system_stop_alarms_press_fn(hub: AlarmHub, resource_id: str) -> None:
    """Stop all alarms on the active system."""

    await hub.api.systems.stop_alarms(resource_id)


async def system_clear_alarms_in_memory_press_fn(hub: AlarmHub, resource_id: str) -> None:
    """Clear alarms in memory on the active system."""

    await hub.api.systems.clear_alarms_in_memory(resource_id)


@callback
def smoke_reset_supported_fn(hub: AlarmHub, resource_id: str) -> bool:
    """Check if a smoke reset button is supported."""

    resource = hub.api.sensors.get(resource_id)
    if resource is None:
        return False

    return resource.attributes.device_type == pyadc.sensor.SensorSubtype.SMOKE_DETECTOR


async def smoke_reset_press_fn(hub: AlarmHub, resource_id: str) -> None:
    """Clear a smoke sensor status on the parent system."""

    resource = hub.api.sensors.get(resource_id)
    if resource is None:
        return

    system_id = resource.system_id or hub.api.active_system.id
    await hub.api.systems.clear_smoke_sensor(system_id, resource_id)


ENTITY_DESCRIPTIONS: list[AdcEntityDescription] = [
    AdcButtonDescription(
        key="debug",
        name="Debug",
        has_entity_name=False,
        controller_fn=lambda hub, resource_id: hub.api.get_controller(resource_id),
        available_fn=lambda hub, resource_id: True,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda hub, resource_id: hub.hass.bus.async_fire(
            DEBUG_REQ_EVENT, {"resource_id": resource_id}
        ),
        supported_fn=_device_exists_in_registry,
        icon="mdi:bug",
    ),
    AdcButtonDescription(
        key="clear_smoke_sensor",
        name="Clear Smoke Sensor",
        controller_fn=lambda hub, _: hub.api.sensors,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=smoke_reset_press_fn,
        supported_fn=smoke_reset_supported_fn,
        icon="mdi:smoke-detector-off",
    ),
]


class AdcButtonEntity(AdcEntity[AdcManagedDeviceT, AdcControllerT], ButtonEntity):
    """Base Alarm.com binary sensor entity."""

    entity_description: AdcButtonDescription

    async def async_press(self) -> None:
        """Press the button."""

        result = self.entity_description.press_fn(self.hub, self.resource_id)
        if isawaitable(result):
            await result

    @callback
    def update_state(self, message: pyadc.EventBrokerMessage | None = None) -> None:
        """Update entity state."""
        return


class AdcSystemButtonEntity(ButtonEntity):
    """Alarm.com system-level button entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        hub: AlarmHub,
        resource_id: str,
        key: str,
        name: str,
        icon: str,
        press_fn: Callable[[AlarmHub, str], Awaitable[Any] | Any],
    ) -> None:
        """Initialize the system button."""

        self.hub = hub
        self.resource_id = resource_id
        self._press_fn = press_fn
        self._attr_name = f"{hub.api.active_system.name} {name}"
        self._attr_unique_id = f"{resource_id}_{key}"
        self._attr_icon = icon
        self._attr_available = hub.available
        self._attr_device_info = {"identifiers": {(DOMAIN, resource_id)}}

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        self.async_on_remove(self.hub.api.subscribe(self.event_handler))

    @callback
    def event_handler(self, message: pyadc.EventBrokerMessage) -> None:
        """Handle event message."""

        if message.topic == pyadc.EventBrokerTopic.CONNECTION_EVENT:
            self._attr_available = self.hub.available
            self.async_write_ha_state()

    async def async_press(self) -> None:
        """Press the button."""

        result = self._press_fn(self.hub, self.resource_id)
        if isawaitable(result):
            await result
