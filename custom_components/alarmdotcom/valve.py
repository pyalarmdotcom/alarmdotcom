"""Interfaces with Alarm.com water valves."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic

import pyalarmdotcomajax as pyadc
from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DATA_HUB, DOMAIN
from .entity import AdcControllerT, AdcEntity, AdcEntityDescription, AdcManagedDeviceT
from .util import cleanup_orphaned_entities_and_devices

if TYPE_CHECKING:
    from .hub import AlarmHub

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the valve platform."""

    hub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id][DATA_HUB]

    entities = [
        AdcValveEntity(hub=hub, resource_id=resource.id, description=entity_description)
        for entity_description in ENTITY_DESCRIPTIONS
        for resource in hub.api.water_valves
        if entity_description.supported_fn(hub, resource.id)
    ]
    async_add_entities(entities)

    current_entity_ids = {entity.entity_id for entity in entities}
    current_unique_ids = {
        uid for uid in (entity.unique_id for entity in entities) if uid is not None
    }
    await cleanup_orphaned_entities_and_devices(
        hass, config_entry, current_entity_ids, current_unique_ids, "valve"
    )


@callback
def is_closed_fn(controller: pyadc.WaterValveController, valve_id: str) -> bool | None:
    """Return whether the valve is closed."""
    resource = controller.get(valve_id)
    if resource is None:
        return None
    return resource.attributes.state == pyadc.water_valve.WaterValveState.CLOSED


@callback
def device_class_fn() -> ValveDeviceClass:
    """Return the device class for the valve."""
    return ValveDeviceClass.WATER


@callback
def supported_features_fn() -> ValveEntityFeature:
    """Return the supported features for the valve."""
    return ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE


@callback
async def control_fn(
    controller: pyadc.WaterValveController,
    valve_id: str,
    command: str,
) -> None:
    """Open or close the valve."""
    try:
        if command == "open":
            await controller.open(valve_id)
        elif command == "close":
            await controller.close(valve_id)
        else:
            raise ValueError(f"Unsupported command: {command}")
    except (pyadc.ServiceUnavailable, pyadc.UnexpectedResponse) as err:
        log.error("Failed to execute valve command: %s", err)
        raise


@dataclass(frozen=True, kw_only=True)
class AdcValveEntityDescription(
    Generic[AdcManagedDeviceT, AdcControllerT],
    AdcEntityDescription[AdcManagedDeviceT, AdcControllerT],
    ValveEntityDescription,
):
    """Base Alarm.com water valve entity description."""

    is_closed_fn: Callable[[AdcControllerT, str], bool | None]
    device_class_fn: Callable[[], ValveDeviceClass]
    supported_features_fn: Callable[[], ValveEntityFeature]
    control_fn: Callable[[AdcControllerT, str, str], Coroutine[Any, Any, None]]


ENTITY_DESCRIPTIONS: list[AdcEntityDescription] = [
    AdcValveEntityDescription[pyadc.water_valve.WaterValve, pyadc.WaterValveController](
        key="water_valve",
        controller_fn=lambda hub, _: hub.api.water_valves,
        is_closed_fn=is_closed_fn,
        device_class_fn=device_class_fn,
        supported_features_fn=supported_features_fn,
        control_fn=control_fn,
    ),
]


class AdcValveEntity(AdcEntity[AdcManagedDeviceT, AdcControllerT], ValveEntity):
    """Base Alarm.com water valve entity."""

    entity_description: AdcValveEntityDescription

    @callback
    def initiate_state(self) -> None:
        """Initiate entity state."""
        self._attr_is_closed = self.entity_description.is_closed_fn(
            self.controller, self.resource_id
        )
        self._attr_device_class = self.entity_description.device_class_fn()
        self._attr_supported_features = self.entity_description.supported_features_fn()
        super().initiate_state()

    @callback
    def update_state(self, message: pyadc.EventBrokerMessage | None = None) -> None:
        """Update entity state."""
        if isinstance(message, pyadc.ResourceEventMessage):
            self._attr_is_closed = self.entity_description.is_closed_fn(
                self.controller, self.resource_id
            )

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve."""
        await self.entity_description.control_fn(
            self.controller, self.resource_id, "open"
        )

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close the valve."""
        await self.entity_description.control_fn(
            self.controller, self.resource_id, "close"
        )
