"""Alarmdotcom implementation of an HA light."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import core
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from typing_extensions import NotRequired

from .base_device import IntBaseDevice
from .const import DEBUG_REQ_EVENT
from .const import DOMAIN

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the button platform."""

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        IntDebugButton(
            coordinator=coordinator,
            device_data=coordinator.data.get("entity_data", {}).get(device_id),
        )
        for device_id in coordinator.data.get("debug_ids", [])
    )


class IntDebugButton(IntBaseDevice, ButtonEntity):  # type: ignore
    """Integration Light Entity."""

    _attr_icon = "mdi:bug"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    class DataStructure(IntBaseDevice.DataStructure):
        """Dict for an ADCI debug button."""

        system_id: NotRequired[str]
        parent_id: str

    def __init__(
        self, coordinator: DataUpdateCoordinator, device_data: DataStructure
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, device_data)

        self._device = device_data

        log.debug(
            "%s: Initializing Alarm.com debug entity for %s.",
            __name__,
            self.unique_id,
        )

    @property
    def device_info(self) -> dict[str, Any]:
        """Return info to categorize this entity as a device."""

        # Associate with parent device.
        return {
            "identifiers": {(DOMAIN, self._device.get("parent_id"))},
        }

    async def async_press(self) -> None:
        """Handle the button press."""

        self.hass.bus.async_fire(
            DEBUG_REQ_EVENT, {"device_id": self._device.get("parent_id")}
        )
