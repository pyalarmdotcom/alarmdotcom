"""Alarmdotcom implementation of an HA cover (garage door)."""
from __future__ import annotations

from collections.abc import Callable
from enum import Enum
import logging
from typing import Any

from homeassistant import core
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.cover import CoverEntity
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyalarmdotcomajax.devices import GarageDoor as pyadcGarageDoor

from .base_device import IntBaseDevice
from .const import DOMAIN

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        IntCover(
            coordinator=coordinator,
            device_data=coordinator.data.get("entity_data", {}).get(device_id),
        )
        for device_id in coordinator.data.get("garage_door_ids", [])
    )


class IntCover(IntBaseDevice, CoverEntity):  # type: ignore
    """Integration Cover Entity."""

    _device_type_name: str = "Garage Door"

    class DataStructure(IntBaseDevice.DataStructure):
        """Dict for an ADCI garage door."""

        desired_state: Enum
        raw_state_text: str
        state: pyadcGarageDoor.DeviceState
        async_open_callback: Callable
        async_close_callback: Callable
        parent_id: str
        read_only: bool

    def __init__(
        self, coordinator: DataUpdateCoordinator, device_data: DataStructure
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, device_data)

        self._device = device_data
        self._attr_device_class: CoverDeviceClass = CoverDeviceClass.GARAGE
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )

        try:
            self.async_open_callback: Callable = self._device["async_open_callback"]
            self.async_close_callback: Callable = self._device["async_close_callback"]
        except KeyError:
            log.error("Failed to initialize control functions for %s.", self.unique_id)
            self._attr_available = False

        log.debug(
            "%s: Initializing Alarm.com garage door entity for garage door %s.",
            __name__,
            self.unique_id,
        )

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""

        if self._device.get("state") == pyadcGarageDoor.DeviceState.OPEN:
            return False

        if self._device.get("state") == pyadcGarageDoor.DeviceState.CLOSED:
            return True

        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        try:
            await self.async_open_callback()
        except PermissionError:
            self._show_permission_error("open")

        await self.coordinator.async_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        try:
            await self.async_close_callback()
        except PermissionError:
            self._show_permission_error("close")

        await self.coordinator.async_refresh()
