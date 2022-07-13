"""Alarmdotcom implementation of an HA light."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import core
from homeassistant.components import light
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from pyalarmdotcomajax.devices import BaseDevice as libBaseDevice
from pyalarmdotcomajax.devices.light import Light as libLight

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
    """Set up the light platform."""

    alarmhub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Light(
            alarmhub=alarmhub,
            device=device,
        )
        for device in alarmhub.system.lights
    )


class Light(HardwareBaseDevice, LightEntity):  # type: ignore
    """Integration Light Entity."""

    _device_type_name: str = "Light"
    _device: libLight

    def __init__(
        self,
        alarmhub: AlarmHub,
        device: libBaseDevice,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(alarmhub, device, device.partition_id)

        self._attr_supported_color_modes = (
            [light.COLOR_MODE_BRIGHTNESS]
            if self._device.brightness
            else [light.COLOR_MODE_ONOFF]
        )

        self._attr_supported_features = light.SUPPORT_BRIGHTNESS

        self._attr_color_mode = (
            light.COLOR_MODE_BRIGHTNESS
            if self._device.brightness
            else light.COLOR_MODE_ONOFF
        )

        self._attr_assumed_state = self._device.supports_state_tracking is True

    @callback  # type: ignore
    def update_device_data(self) -> None:
        """Update the entity when coordinator is updated."""

        self._attr_is_on = self._determine_is_on(self._device.state)
        self._attr_brightness = (
            int((raw_bright * 255) / 100)
            if (raw_bright := self._device.brightness)
            else None
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light or adjust brightness."""

        brightness: int | None = None
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int((kwargs[ATTR_BRIGHTNESS] / 255) * 100)

        try:
            await self._device.async_turn_on(brightness)
        except PermissionError:
            self._show_permission_error("turn on")

        await self._alarmhub.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""

        try:
            await self._device.async_turn_off()
        except PermissionError:
            self._show_permission_error("turn off")

        await self._alarmhub.coordinator.async_refresh()

    #
    # Helpers
    #

    def _determine_is_on(self, state: libLight.DeviceState) -> bool | None:
        """Return True if entity is on."""

        log.debug("Processing state %s for %s", state, self.name)

        if not self._device.malfunction:
            if state in [
                libLight.DeviceState.ON,
                libLight.DeviceState.LEVELCHANGE,
            ]:
                return True

            if state == libLight.DeviceState.OFF:
                return False

            log.error(
                "Cannot determine light state. Found raw state of %s.",
                state,
            )

        return None
