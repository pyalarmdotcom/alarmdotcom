"""Alarmdotcom implementation of an HA switch."""
from __future__ import annotations

import logging

from homeassistant import core
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from pyalarmdotcomajax.extensions import (
    CameraSkybellControllerExtension as libCameraSkybellControllerExtension,
)
from pyalarmdotcomajax.extensions import ConfigurationOption as libConfigurationOption
from pyalarmdotcomajax.extensions import (
    ConfigurationOptionType as libConfigurationOptionType,
)

from .alarmhub import AlarmHub
from .base_device import ConfigBaseDevice
from .const import DOMAIN

log = logging.getLogger(__name__)

# TODO: This device contains behavior to the Skybell HD. It needs to be made more generic as other devices are supported.


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    alarmhub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id]

    for device in alarmhub.system.cameras:
        async_add_entities(
            ConfigOptionSwitch(
                alarmhub=alarmhub,
                device=device,
                config_option=config_option,
            )
            for config_option in device.settings.values()
            if isinstance(config_option, libConfigurationOption)
            and config_option.option_type is libConfigurationOptionType.BINARY_CHIME
        )


class ConfigOptionSwitch(ConfigBaseDevice, SwitchEntity):  # type: ignore
    """Integration Switch Entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    @callback  # type: ignore
    def update_device_data(self) -> None:
        """Update the entity when coordinator is updated."""

        self._attr_is_on = (
            self._config_option.current_value
            is libCameraSkybellControllerExtension.ChimeOnOff.ON
        )

        self._attr_icon = self._determine_icon()

    def _determine_icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if self._config_option.option_type is libConfigurationOptionType.BINARY_CHIME:
            return "mdi:bell" if self.is_on else "mdi:bell-off"

        return super().icon if isinstance(super().icon, str) else None

    async def async_turn_on(self, **kwargs) -> None:  # type: ignore
        """Turn on."""
        await self._device.async_change_setting(
            self._config_option.slug,
            libCameraSkybellControllerExtension.ChimeOnOff.ON,
        )

        await self._alarmhub.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore
        """Turn off."""
        await self._device.async_change_setting(
            self._config_option.slug,
            libCameraSkybellControllerExtension.ChimeOnOff.OFF,
        )

        await self._alarmhub.coordinator.async_refresh()
