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

    # Log discovered devices for debugging
    log.debug(
        "Setting up cover platform. Found %d garage doors and %d gates.",
        len(hub.api.garage_doors),
        len(hub.api.gates),
    )
    for device in hub.api.garage_doors:
        log.debug("  - Garage door: %s (ID: %s)", device.name, device.id)
    for device in hub.api.gates:
        log.debug("  - Gate: %s (ID: %s)", device.name, device.id)

    entities = [
        AdcCoverEntity(hub=hub, resource_id=resource.id, description=entity_description)
        for entity_description in ENTITY_DESCRIPTIONS
        for resource in hub.api.garage_doors + hub.api.gates
        if entity_description.supported_fn(hub, resource.id)
    ]

    log.info("Created %d cover entities.", len(entities))
    async_add_entities(entities)

    current_entity_ids = {entity.entity_id for entity in entities}
    current_unique_ids = {
        uid for uid in (entity.unique_id for entity in entities) if uid is not None
    }
    await cleanup_orphaned_entities_and_devices(
        hass, config_entry, current_entity_ids, current_unique_ids, "cover"
    )


@callback
def garage_door_supported_fn(hub: AlarmHub, resource_id: str) -> bool:
    """Check if the resource is a garage door."""
    is_supported = hub.api.garage_doors.get(resource_id) is not None
    if is_supported:
        device = hub.api.managed_devices.get(resource_id)
        log.debug(
            "Resource %s (%s) matched as garage_door",
            resource_id,
            device.name if device else "unknown",
        )
    return is_supported


@callback
def gate_supported_fn(hub: AlarmHub, resource_id: str) -> bool:
    """Check if the resource is a gate."""
    is_supported = hub.api.gates.get(resource_id) is not None
    if is_supported:
        device = hub.api.managed_devices.get(resource_id)
        log.debug(
            "Resource %s (%s) matched as gate",
            resource_id,
            device.name if device else "unknown",
        )
    return is_supported


@callback
def is_closed_fn(
    controller: pyadc.GarageDoorController | pyadc.GateController, door_id: str
) -> bool | None:
    """Return whether the garage door is closed."""
    resource = controller.get(door_id)
    if resource is None:
        log.debug(
            "is_closed_fn: Resource %s not found in controller %s",
            door_id,
            type(controller).__name__,
        )
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
    # Verify resource exists before attempting control
    resource = controller.get(door_id)
    if resource is None:
        log.error(
            "Cannot execute command '%s': Resource %s not found in controller %s",
            command,
            door_id,
            type(controller).__name__,
        )
        raise ValueError(f"Resource {door_id} not found in controller")

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
        supported_fn=garage_door_supported_fn,
        is_closed_fn=is_closed_fn,
        device_class_fn=device_class_fn,
        supported_features_fn=supported_features_fn,
        control_fn=control_fn,
    ),
    AdcCoverEntityDescription[pyadc.gate.Gate, pyadc.GateController](
        key="gate",
        controller_fn=lambda hub, _: hub.api.gates,
        supported_fn=gate_supported_fn,
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

        # Verify the resource exists in the assigned controller
        resource = self.controller.get(self.resource_id)
        if resource is None:
            device = self.hub.api.managed_devices.get(self.resource_id)
            device_name = device.name if device else "unknown"
            log.error(
                "Resource %s (%s) not found in %s controller during initialization. "
                "This may indicate a controller/device type mismatch.",
                self.resource_id,
                device_name,
                self.entity_description.key,
            )
            # Mark entity as unavailable if resource not found in controller
            self._attr_available = False
            self._attr_is_closed = None
        else:
            log.debug(
                "Initializing cover entity for %s (resource_id: %s) using %s controller",
                resource.name,
                self.resource_id,
                self.entity_description.key,
            )
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
            # Verify resource still exists in controller before updating
            resource = self.controller.get(self.resource_id)
            if resource is None:
                log.warning(
                    "Resource %s not found in %s controller during state update. Marking unavailable.",
                    self.resource_id,
                    self.entity_description.key,
                )
                self._attr_available = False
                self._attr_is_closed = None
            else:
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
