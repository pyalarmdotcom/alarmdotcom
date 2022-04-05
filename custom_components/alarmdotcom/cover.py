"""Alarmdotcom implementation of an HA cover (garage door)."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant import core
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.cover import CoverEntity
from homeassistant.components.cover import SUPPORT_CLOSE
from homeassistant.components.cover import SUPPORT_OPEN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from pyalarmdotcomajax.entities import ADCGarageDoor

from . import ADCIEntity
from . import const as adci
from .controller import ADCIController

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    controller: ADCIController = hass.data[adci.DOMAIN][config_entry.entry_id]

    async_add_entities(
        ADCICover(controller, controller.devices.get("entity_data", {}).get(garage_id))  # type: ignore
        for garage_id in controller.devices.get("garage_door_ids", [])
    )


class ADCICover(ADCIEntity, CoverEntity):  # type: ignore
    """Integration Cover Entity."""

    def __init__(
        self, controller: ADCIController, device_data: adci.ADCIGarageDoorData
    ):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(controller, device_data)

        self._device: adci.ADCIGarageDoorData = device_data
        self._attr_device_class: CoverDeviceClass = CoverDeviceClass.GARAGE
        self._attr_supported_features = SUPPORT_OPEN | SUPPORT_CLOSE

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

        if self._device.get("state") == ADCGarageDoor.DeviceState.OPEN:
            return False

        if self._device.get("state") == ADCGarageDoor.DeviceState.CLOSED:
            return True

        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        try:
            await self.async_open_callback()
        except PermissionError:
            self._show_permission_error("open")

        await self._controller.async_coordinator_update(critical=False)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        try:
            await self.async_close_callback()
        except PermissionError:
            self._show_permission_error("close")

        await self._controller.async_coordinator_update(critical=False)
