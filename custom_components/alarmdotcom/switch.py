"""Alarmdotcom implementation of an HA switch."""
from __future__ import annotations

import logging

from homeassistant import core
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback, DiscoveryInfoType
from pyalarmdotcomajax.extensions import (
    CameraSkybellControllerExtension as libCameraSkybellControllerExtension,
)
from pyalarmdotcomajax.extensions import ConfigurationOption as libConfigurationOption
from pyalarmdotcomajax.extensions import (
    ConfigurationOptionType as libConfigurationOptionType,
)

from .base_device import ConfigBaseDevice
from .const import DATA_CONTROLLER, DOMAIN
from .controller import AlarmIntegrationController

LOGGER = logging.getLogger(__name__)

# TODO: This device contains behavior specific to the Skybell HD. It needs to be made more generic as other devices are supported.


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    controller: AlarmIntegrationController = hass.data[DOMAIN][config_entry.entry_id][DATA_CONTROLLER]

    for device in controller.api.devices.cameras.values():
        async_add_entities(
            ConfigOptionSwitch(
                controller=controller,
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

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._config_option.current_value is libCameraSkybellControllerExtension.ChimeOnOff.ON

    @property
    def icon(self) -> str | None:
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

        await self._controller.update_coordinator.async_refresh()

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore
        """Turn off."""
        await self._device.async_change_setting(
            self._config_option.slug,
            libCameraSkybellControllerExtension.ChimeOnOff.OFF,
        )

        await self._controller.update_coordinator.async_refresh()
