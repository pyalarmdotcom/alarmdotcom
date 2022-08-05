"""Alarmdotcom implementation of an HA thermostat."""
from __future__ import annotations

import logging

from homeassistant import core
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.components.climate import HVACMode
from homeassistant.components.climate.const import ATTR_HVAC_MODE
from homeassistant.components.climate.const import ATTR_TARGET_TEMP_HIGH
from homeassistant.components.climate.const import ATTR_TARGET_TEMP_LOW
from homeassistant.components.climate.const import FAN_AUTO
from homeassistant.components.climate.const import FAN_ON
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.const import TEMP_FAHRENHEIT
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from pyalarmdotcomajax.devices import BaseDevice as libBaseDevice
from pyalarmdotcomajax.devices.thermostat import Thermostat as libThermostat

from .alarmhub import AlarmHub
from .base_device import HardwareBaseDevice
from .const import DOMAIN

log = logging.getLogger(__name__)

FAN_CIRCULATE = "Circulate"


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the light platform."""

    alarmhub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Climate(
            alarmhub=alarmhub,
            device=device,
        )
        for device in alarmhub.system.thermostats
    )


class Climate(HardwareBaseDevice, ClimateEntity):  # type: ignore
    """Integration Climate Entity."""

    _device_type_name: str = "Thermostat"
    _device: libThermostat

    _attr_temperature_unit = TEMP_FAHRENHEIT  # Alarm.com always returns Fahrenheit, even when user profile is set to C. Conversion happens on frontend.

    def __init__(
        self,
        alarmhub: AlarmHub,
        device: libBaseDevice,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(alarmhub, device, device.partition_id)

        self._raw_attribs = self._device.attributes

        self._attr_target_temperature_step = 1.0

        self._determine_features()

    @callback  # type: ignore
    def update_device_data(self) -> None:
        """Update the entity when coordinator is updated."""

        self._raw_attribs = self._device.attributes

        #
        # Reported Values
        #

        self._attr_current_temperature = self._raw_attribs.temp_average

        if self._raw_attribs.supports_humidity:
            self._attr_current_humidity = self._raw_attribs.humidity

        #
        # HVAC Mode
        #

        # Set HVAC mode
        if self._device.state in [
            libThermostat.DeviceState.AUX_HEAT,
            libThermostat.DeviceState.HEAT,
        ]:
            self._attr_hvac_mode = HVACMode.HEAT
        elif self._device.state == libThermostat.DeviceState.COOL:
            self._attr_hvac_mode = HVACMode.COOL
        elif self._device.state == libThermostat.DeviceState.AUTO:
            self._attr_hvac_mode = HVACMode.HEAT_COOL
        elif (
            self._device.state == libThermostat.DeviceState.OFF
            and self._raw_attribs.fan_mode == libThermostat.FanMode.ON
        ):
            self._attr_hvac_mode = HVACMode.FAN_ONLY
        elif self._device.state == libThermostat.DeviceState.OFF:
            self._attr_hvac_mode = HVACMode.OFF
        else:
            self._attr_hvac_mode = None

        #
        # Target Temps
        #

        # Reset all temperature target parameters before re-setting.
        self._attr_target_temperature_high = None
        self._attr_target_temperature_low = None
        self._attr_target_temperature = None
        self._attr_max_temp = None
        self._attr_min_temp = None

        # Set target temperature parameters
        if not self._raw_attribs.supports_setpoints:
            pass
        elif self._device.state in [
            libThermostat.DeviceState.AUX_HEAT,
            libThermostat.DeviceState.HEAT,
        ]:
            self._attr_target_temperature = self._raw_attribs.heat_setpoint
            self._attr_max_temp = self._raw_attribs.max_heat_setpoint
            self._attr_min_temp = self._raw_attribs.min_heat_setpoint
        elif self._device.state == libThermostat.DeviceState.COOL:
            self._attr_target_temperature = self._raw_attribs.cool_setpoint
            self._attr_max_temp = self._raw_attribs.max_cool_setpoint
            self._attr_min_temp = self._raw_attribs.min_cool_setpoint
        elif self._device.state == libThermostat.DeviceState.AUTO:
            self._attr_target_temperature_high = self._raw_attribs.cool_setpoint
            self._attr_target_temperature_low = self._raw_attribs.heat_setpoint
            self._attr_max_temp = self._raw_attribs.max_cool_setpoint
            self._attr_min_temp = self._raw_attribs.min_heat_setpoint

        #
        # Fan Mode
        #

        if self._raw_attribs.fan_mode == libThermostat.FanMode.AUTO:
            self._attr_fan_mode = FAN_AUTO
        elif self._raw_attribs.fan_mode == libThermostat.FanMode.ON:
            self._attr_fan_mode = FAN_ON
        else:
            self._attr_fan_mode = None

        #
        # Aux Heat
        #

        self._attr_is_aux_heat = (
            self._device.state == libThermostat.DeviceState.AUX_HEAT
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn on the light or adjust brightness."""

        try:
            if hvac_mode == HVACMode.COOL:
                await self._device.async_set_attribute(
                    state=libThermostat.DeviceState.COOL
                )
            elif hvac_mode == HVACMode.HEAT:
                await self._device.async_set_attribute(
                    state=libThermostat.DeviceState.HEAT
                )
            elif hvac_mode == HVACMode.HEAT_COOL:
                await self._device.async_set_attribute(
                    state=libThermostat.DeviceState.AUTO
                )
            elif hvac_mode == HVACMode.FAN_ONLY:
                await self._device.async_set_attribute(
                    state=libThermostat.DeviceState.OFF
                )
                await self.async_set_fan_mode(FAN_ON)
            elif hvac_mode == HVACMode.OFF:
                await self._device.async_set_attribute(
                    state=libThermostat.DeviceState.OFF
                )
                await self.async_set_fan_mode(FAN_AUTO)
        except PermissionError:
            self._show_permission_error("set")

        await self._alarmhub.coordinator.async_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Change fan mode."""

        max_fan_duration = (
            0
            if self._raw_attribs.supports_fan_indefinite
            else max(self._raw_attribs.supported_fan_durations)
        )

        try:
            if fan_mode == FAN_ON:
                await self._device.async_set_attribute(
                    fan=(libThermostat.FanMode.ON, max_fan_duration)
                )
            elif fan_mode == FAN_AUTO:
                await self._device.async_set_attribute(
                    fan=(libThermostat.FanMode.AUTO, 0)
                )
        except PermissionError:
            self._show_permission_error("set")

        await self._alarmhub.coordinator.async_refresh()

    async def async_set_temperature(self, **kwargs) -> None:  # type: ignore
        """Set new target temperature."""

        # Change HVAC Mode First
        if hvac_mode := kwargs.get(ATTR_HVAC_MODE):
            await self.async_set_hvac_mode(hvac_mode)
            await self.async_update()

        # Heat/cool setpoint
        heat_setpoint = None
        cool_setpoint = None
        if self.hvac_mode == HVACMode.HEAT:
            heat_setpoint = kwargs.get(ATTR_TEMPERATURE)
        elif self.hvac_mode == HVACMode.COOL:
            cool_setpoint = kwargs.get(ATTR_TEMPERATURE)
        else:
            heat_setpoint = kwargs.get(ATTR_TARGET_TEMP_LOW)
            cool_setpoint = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        if heat_setpoint is not None:
            await self._device.async_set_attribute(heat_setpoint=heat_setpoint)
        if cool_setpoint is not None:
            await self._device.async_set_attribute(cool_setpoint=cool_setpoint)

    def _determine_features(self) -> None:
        """Determine which features are available for thermostat."""

        #
        # SUPPORTED FEATURES
        #

        supported_features = 0

        if self._raw_attribs.supports_setpoints:
            supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

        if self._raw_attribs.supports_auto:
            supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

        if self._raw_attribs.supports_fan_mode:
            supported_features |= ClimateEntityFeature.FAN_MODE

        if self._raw_attribs.supports_heat_aux:
            supported_features |= ClimateEntityFeature.AUX_HEAT

        self._attr_supported_features = supported_features

        #
        # HVAC MODES
        #

        hvac_modes = [HVACMode.OFF]

        if self._raw_attribs.supports_heat:
            hvac_modes.append(HVACMode.HEAT)

        if self._raw_attribs.supports_cool:
            hvac_modes.append(HVACMode.COOL)

        if self._raw_attribs.supports_auto:
            hvac_modes.append(HVACMode.HEAT_COOL)

        if self._raw_attribs.supports_fan_mode:
            hvac_modes.append(HVACMode.FAN_ONLY)

        self._attr_hvac_modes = hvac_modes

        #
        # FAN MODES
        #

        if self._raw_attribs.supports_fan_mode:
            self._attr_fan_modes = [FAN_AUTO, FAN_ON]
