"""Alarmdotcom implementation of an HA number."""
from __future__ import annotations

import logging

from homeassistant import core
from homeassistant.components.number import NumberEntity
from homeassistant.components.number import NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from pyalarmdotcomajax.devices import BaseDevice as libBaseDevice
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
    """Set up the sensor platform."""

    alarmhub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id]

    for device in alarmhub.system.cameras:
        async_add_entities(
            ConfigOptionNumber(
                alarmhub=alarmhub,
                device=device,
                config_option=config_option,
            )
            for config_option in device.settings.values()
            if isinstance(config_option, libConfigurationOption)
            and config_option.option_type is libConfigurationOptionType.BRIGHTNESS
        )


class ConfigOptionNumber(ConfigBaseDevice, NumberEntity):  # type: ignore
    """Integration Number Entity."""

    def __init__(
        self,
        alarmhub: AlarmHub,
        device: libBaseDevice,
        config_option: libConfigurationOption,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(alarmhub, device, config_option)

        if self._config_option.value_max:
            self._attr_native_max_value: float = self._config_option.value_max

        if self._config_option.value_min:
            self._attr_native_min_value: float = self._config_option.value_min

        if self._config_option.value_max and self._config_option.value_min:
            self._attr_mode = NumberMode.SLIDER
        else:
            self._attr_mode = NumberMode.AUTO

    def _determine_icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if self._config_option.option_type == libConfigurationOptionType.BRIGHTNESS:
            return "mdi:brightness-5"

        return super().icon if isinstance(super().icon, str) else None

    @callback  # type: ignore
    def update_device_data(self) -> None:
        """Update the entity when coordinator is updated."""

        if current_value := self._config_option.current_value:
            self._attr_native_value = float(current_value)

        self._attr_icon = self._determine_icon()

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self._device.async_change_setting(self._config_option.slug, int(value))
