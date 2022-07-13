"""Alarmdotcom implementation of an HA cover (garage door)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import core
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.cover import CoverEntity
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from pyalarmdotcomajax.devices import BaseDevice as libBaseDevice
from pyalarmdotcomajax.devices.garage_door import GarageDoor as libGarageDoor

from .alarmhub import AlarmHub
from .base_device import HardwareBaseDevice
from .const import DOMAIN

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the cover platform."""

    alarmhub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Cover(
            alarmhub=alarmhub,
            device=device,
        )
        for device in alarmhub.system.garage_doors
    )


class Cover(HardwareBaseDevice, CoverEntity):  # type: ignore
    """Integration Cover Entity."""

    _device_type_name: str = "Garage Door"
    _device: libGarageDoor

    def __init__(
        self,
        alarmhub: AlarmHub,
        device: libBaseDevice,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(alarmhub, device, device.partition_id)

        self._attr_device_class: CoverDeviceClass = CoverDeviceClass.GARAGE
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )

    @callback  # type: ignore
    def update_device_data(self) -> None:
        """Update the entity when coordinator is updated."""

        self._attr_is_closed = self._determine_is_closed(self._device.state)
        self._attr_is_closing = False
        self._attr_is_opening = False

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""

        self._attr_is_opening = True

        try:
            await self._device.async_open()
        except PermissionError:
            self._show_permission_error("open")

        await self._alarmhub.coordinator.async_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""

        self._attr_is_closing = True

        try:
            await self._device.async_close()
        except PermissionError:
            self._show_permission_error("close")

        await self._alarmhub.coordinator.async_refresh()

    #
    # Helpers
    #

    def _determine_is_closed(self, state: libGarageDoor.DeviceState) -> bool | None:
        """Return if the cover is closed or not."""

        if not self._device.malfunction:

            if state == libGarageDoor.DeviceState.OPEN:
                return False

            if state == libGarageDoor.DeviceState.CLOSED:
                return True

            log.error(
                "Cannot determine light state. Found raw state of %s.",
                state,
            )

        return None
