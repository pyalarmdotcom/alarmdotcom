"""Interfaces with Alarm.com garage doors."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic

import pyalarmdotcomajax as pyadc
from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
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
    """Set up the cover platform."""

    hub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id][DATA_HUB]

    entities = [
        AdcCoverEntity(hub=hub, resource_id=resource.id, description=entity_description)
        for entity_description in ENTITY_DESCRIPTIONS
        for resource in hub.api.garage_doors + hub.api.gates
        if entity_description.supported_fn(hub, resource.id)
    ]
    async_add_entities(entities)

    current_entity_ids = {entity.entity_id for entity in entities}
    current_unique_ids = {
        uid for uid in (entity.unique_id for entity in entities) if uid is not None
    }
    await cleanup_orphaned_entities_and_devices(
        hass, config_entry, current_entity_ids, current_unique_ids, "cover"
    )


@callback
def is_closed_fn(
    controller: pyadc.GarageDoorController | pyadc.GateController, door_id: str
) -> bool | None:
    """Return whether the garage door is closed."""
    resource = controller.get(door_id)
    if resource is None:
        return None
    return resource.attributes.state in [
        pyadc.garage_door.GarageDoorState.CLOSED,
        pyadc.gate.GateState.CLOSED,
    ]


@callback
def device_class_fn() -> CoverDeviceClass:
    """Return the device class for the garage door."""
    return CoverDeviceClass.GARAGE


@callback
def supported_features_fn() -> CoverEntityFeature:
    """Return the supported features for the garage door."""
    return CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE


@callback
async def control_fn(
    controller: pyadc.GarageDoorController | pyadc.GateController,
    door_id: str,
    command: str,
) -> None:
    """Open or close the garage door."""
    try:
        if command == "open":
            await controller.open(door_id)
        elif command == "close":
            await controller.close(door_id)
        else:
            raise ValueError(f"Unsupported command: {command}")
    except (pyadc.ServiceUnavailable, pyadc.UnexpectedResponse) as err:
        log.error("Failed to execute garage door command: %s", err)
        raise


@dataclass(frozen=True, kw_only=True)
class AdcCoverEntityDescription(
    Generic[AdcManagedDeviceT, AdcControllerT],
    AdcEntityDescription[AdcManagedDeviceT, AdcControllerT],
    CoverEntityDescription,
):
    """Base Alarm.com garage door entity description."""

    is_closed_fn: Callable[[AdcControllerT, str], bool | None]
    """Return whether the garage door is closed."""
    device_class_fn: Callable[[], CoverDeviceClass]
    """Return the device class for the garage door."""
    supported_features_fn: Callable[[], CoverEntityFeature]
    """Return the supported features for the garage door."""
    control_fn: Callable[[AdcControllerT, str, str], Coroutine[Any, Any, None]]
    """Open or close the garage door."""


ENTITY_DESCRIPTIONS: list[AdcEntityDescription] = [
    AdcCoverEntityDescription[pyadc.garage_door.GarageDoor, pyadc.GarageDoorController](
        key="garage_door",
        controller_fn=lambda hub, _: hub.api.garage_doors,
        is_closed_fn=is_closed_fn,
        device_class_fn=device_class_fn,
        supported_features_fn=supported_features_fn,
        control_fn=control_fn,
    ),
    AdcCoverEntityDescription[pyadc.gate.Gate, pyadc.GateController](
        key="gate",
        controller_fn=lambda hub, _: hub.api.gates,
        is_closed_fn=is_closed_fn,
        device_class_fn=device_class_fn,
        supported_features_fn=supported_features_fn,
        control_fn=control_fn,
    ),
]


class AdcCoverEntity(AdcEntity[AdcManagedDeviceT, AdcControllerT], CoverEntity):
    """Base Alarm.com garage door entity."""

    entity_description: AdcCoverEntityDescription

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

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the garage door."""
        await self.entity_description.control_fn(
            self.controller, self.resource_id, "open"
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the garage door."""
        await self.entity_description.control_fn(
            self.controller, self.resource_id, "close"
        )
