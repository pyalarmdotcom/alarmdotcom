"""Alarmdotcom implementation of an HA switch."""
from __future__ import annotations

import logging
from enum import Enum

from homeassistant import core
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback, DiscoveryInfoType
from pyalarmdotcomajax.devices.registry import AllDevices_t
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
    discovery_info: DiscoveryInfoType | None = None,  # pylint: disable=unused-argument
) -> None:
    """Set up the select platform."""

    controller: AlarmIntegrationController = hass.data[DOMAIN][config_entry.entry_id][DATA_CONTROLLER]

    for device in controller.api.devices.cameras.values():
        async_add_entities(
            ConfigOptionSelect(
                controller=controller,
                device=device,
                config_option=config_option,
            )
            for config_option in device.settings.values()
            if isinstance(config_option, libConfigurationOption)
            and config_option.option_type
            in [
                libConfigurationOptionType.ADJUSTABLE_CHIME,
                libConfigurationOptionType.MOTION_SENSITIVITY,
            ]
        )


class ConfigOptionSelect(ConfigBaseDevice, SelectEntity):  # type: ignore
    """Integration configuration option entity."""

    def __init__(
        self,
        controller: AlarmIntegrationController,
        device: AllDevices_t,
        config_option: libConfigurationOption,
    ) -> None:
        """Initialize."""
        super().__init__(controller, device, config_option)

        self._attr_entity_category = EntityCategory.CONFIG

        self._select_options_map: dict[
            str,
            libCameraSkybellControllerExtension.MotionSensitivity
            | libCameraSkybellControllerExtension.ChimeAdjustableVolume,
        ] = {}
        if self._config_option.option_type == libConfigurationOptionType.ADJUSTABLE_CHIME:
            self._select_options_map = {
                member.name.title().replace("_", " "): member
                for member in libCameraSkybellControllerExtension.ChimeAdjustableVolume
            }
        elif self._config_option.option_type == libConfigurationOptionType.MOTION_SENSITIVITY:
            self._select_options_map = {
                member.name.title().replace("_", " "): member
                for member in libCameraSkybellControllerExtension.MotionSensitivity
            }
        else:
            LOGGER.exception(
                "%s: Encountered unknown select configuration type when initializing %s.",
                __name__,
                self.unique_id,
            )

        self._attr_options: list = list(self._select_options_map.keys())

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if self._config_option.option_type == libConfigurationOptionType.ADJUSTABLE_CHIME:
            if (
                current_value := self._config_option.current_value
            ) == libCameraSkybellControllerExtension.ChimeAdjustableVolume.OFF:
                return "mdi:volume-mute"
            if current_value == libCameraSkybellControllerExtension.ChimeAdjustableVolume.LOW:
                return "mdi:volume-low"
            if current_value == libCameraSkybellControllerExtension.ChimeAdjustableVolume.MEDIUM:
                return "mdi:volume-medium"
            if current_value == libCameraSkybellControllerExtension.ChimeAdjustableVolume.HIGH:
                return "mdi:volume-high"
        elif self._config_option.option_type == libConfigurationOptionType.MOTION_SENSITIVITY:
            return "mdi:tune"

        return super().icon if isinstance(super().icon, str) else None

    @property
    def current_option(self) -> str | None:
        """Return the selected option."""

        if isinstance(current_value := self._config_option.current_value, Enum):
            return current_value.name.title().replace("_", " ")
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        await self._device.async_change_setting(self._config_option.slug, self._select_options_map[option])
