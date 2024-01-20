"""Alarmdotcom implementation of an HA light."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant import core
from homeassistant.components import light
from homeassistant.components.light import ATTR_BRIGHTNESS, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback, DiscoveryInfoType
from pyalarmdotcomajax.devices.light import Light as libLight
from pyalarmdotcomajax.exceptions import NotAuthorized

from .base_device import HardwareBaseDevice
from .const import DATA_CONTROLLER, DOMAIN
from .controller import AlarmIntegrationController

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the light platform."""

    controller: AlarmIntegrationController = hass.data[DOMAIN][config_entry.entry_id][DATA_CONTROLLER]

    async_add_entities(
        Light(
            controller=controller,
            device=device,
        )
        for device in controller.api.devices.lights.values()
    )


class Light(HardwareBaseDevice, LightEntity):  # type: ignore
    """Integration Light Entity."""

    _device_type_name: str = "Light"
    _device: libLight

    def __init__(
        self,
        controller: AlarmIntegrationController,
        device: libLight,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(controller, device)

        self._attr_supported_color_modes = (
            [light.COLOR_MODE_BRIGHTNESS] if self._device.brightness else [light.COLOR_MODE_ONOFF]
        )

        self._attr_supported_features = light.SUPPORT_BRIGHTNESS

        self._attr_color_mode = light.COLOR_MODE_BRIGHTNESS if self._device.brightness else light.COLOR_MODE_ONOFF

        self._attr_assumed_state = self._device.supports_state_tracking is False

        # Independently track state for lights that don't support state tracking
        self._local_state: bool | None = None
        self._local_brightness: int | None = None

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""

        return self._local_state

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""

        return self._local_brightness

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light or adjust brightness."""

        brightness: int | None = None
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int((kwargs[ATTR_BRIGHTNESS] / 255) * 100)

        try:
            await self._device.async_turn_on(brightness)
        except NotAuthorized:
            self._show_permission_error("turn on or adjust brightness on")

        if self.assumed_state:
            # optimistically assume that light has changed state
            self._local_state = True
            self._local_brightness = kwargs.get(ATTR_BRIGHTNESS)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""

        try:
            await self._device.async_turn_off()
        except NotAuthorized:
            self._show_permission_error("turn off")

        if self.assumed_state:
            # optimistically assume that light has changed state
            self._local_state = False
            self._local_brightness = None

    def _legacy_refresh_attributes(self) -> None:
        """Perform action whenever device is updated."""

        # Update state
        if not self._device.malfunction and not self.assumed_state:
            match self._device.state:
                case libLight.DeviceState.ON | libLight.DeviceState.LEVELCHANGE:
                    self._local_state = True

                case libLight.DeviceState.OFF:
                    self._local_state = False

            self._local_brightness = (
                int((self._device.brightness * 255) / 100) if self._device.brightness else None
            )
