"""Alarmdotcom implementation of an HA switch."""
from __future__ import annotations

from enum import Enum
import logging

from homeassistant import core
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from pyalarmdotcomajax.devices import BaseDevice as libBaseDevice
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
    discovery_info: DiscoveryInfoType | None = None,  # pylint: disable=unused-argument
) -> None:
    """Set up the select platform."""

    alarmhub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id]

    for device in alarmhub.system.cameras:
        async_add_entities(
            ConfigOptionSelect(
                alarmhub=alarmhub,
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
        alarmhub: AlarmHub,
        device: libBaseDevice,
        config_option: libConfigurationOption,
    ) -> None:
        """Initialize."""
        super().__init__(alarmhub, device, config_option)

        self._attr_entity_category = EntityCategory.CONFIG

        self._select_options_map = {}
        if (
            self._config_option.option_type
            == libConfigurationOptionType.ADJUSTABLE_CHIME
        ):
            self._select_options_map = {
                member.name.title().replace("_", " "): member
                for member in libCameraSkybellControllerExtension.ChimeAdjustableVolume
            }
        elif (
            self._config_option.option_type
            == libConfigurationOptionType.MOTION_SENSITIVITY
        ):
            self._select_options_map = {
                member.name.title().replace("_", " "): member
                for member in libCameraSkybellControllerExtension.MotionSensitivity
            }
        else:
            log.error(
                "%s: Encountered unknown select configuration type when initializing %s.",
                __name__,
                self.unique_id,
            )

        self._attr_options: list = list(self._select_options_map.keys())

        self._attr_current_option: str | None = self._config_option.current_value

    def _determine_icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if (
            self._config_option.option_type
            == libConfigurationOptionType.ADJUSTABLE_CHIME
        ):
            if (
                current_value := self._config_option.current_value
            ) == libCameraSkybellControllerExtension.ChimeAdjustableVolume.OFF:
                return "mdi:volume-mute"
            if (
                current_value
                == libCameraSkybellControllerExtension.ChimeAdjustableVolume.LOW
            ):
                return "mdi:volume-low"
            if (
                current_value
                == libCameraSkybellControllerExtension.ChimeAdjustableVolume.MEDIUM
            ):
                return "mdi:volume-medium"
            if (
                current_value
                == libCameraSkybellControllerExtension.ChimeAdjustableVolume.HIGH
            ):
                return "mdi:volume-high"
        elif (
            self._config_option.option_type
            == libConfigurationOptionType.MOTION_SENSITIVITY
        ):
            return "mdi:tune"

        return super().icon if isinstance(super().icon, str) else None

    @callback  # type: ignore
    def update_device_data(self) -> None:
        """Update the entity when coordinator is updated."""

        if isinstance(current_value := self._config_option.current_value, Enum):
            self._attr_current_option = current_value.name.title().replace("_", " ")

        self._attr_icon = self._determine_icon()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        await self._device.async_change_setting(
            self._config_option.slug, self._select_options_map[option]
        )
