"""Interfaces with Alarm.com thermostats."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic

import pyalarmdotcomajax as pyadc
from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_ON,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
    UnitOfTemperature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DATA_HUB, DOMAIN
from .entity import AdcControllerT, AdcEntity, AdcEntityDescription, AdcManagedDeviceT
from .util import cleanup_orphaned_entities_and_devices

if TYPE_CHECKING:
    from .hub import AlarmHub

FAN_AUTO_LOW = "auto_low"
FAN_AUTO_MED = "auto_medium"
FAN_CIRCULATE = "circulate"
PRESET_MANUAL_MODE = "manual_mode"
PRESET_SCHEDULE_MODE = "schedule_mode"
PRESET_SMART_MODE = "smart_mode"

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the climate platform."""

    hub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id][DATA_HUB]

    entities = [
        AdcClimateEntity(hub=hub, resource_id=device.id, description=entity_description)
        for entity_description in ENTITY_DESCRIPTIONS
        for device in hub.api.thermostats
        if entity_description.supported_fn(hub, device.id)
    ]
    async_add_entities(entities)

    current_entity_ids = {entity.entity_id for entity in entities}
    current_unique_ids = {
        uid for uid in (entity.unique_id for entity in entities) if uid is not None
    }
    await cleanup_orphaned_entities_and_devices(
        hass, config_entry, current_entity_ids, current_unique_ids, "climate"
    )


@callback
def current_humidity_fn(
    controller: pyadc.ThermostatController, thermostat_id: str
) -> int | None:
    """Return the current humidity."""
    resource = controller.get(thermostat_id)
    if resource is None:
        return None
    return resource.attributes.humidity_level


@callback
def current_temperature_fn(
    controller: pyadc.ThermostatController, thermostat_id: str
) -> float | None:
    """Return the current temperature."""
    resource = controller.get(thermostat_id)
    if resource is None:
        return None
    return resource.attributes.ambient_temp


@callback
def fan_mode_fn(
    controller: pyadc.ThermostatController, thermostat_id: str
) -> str | None:
    """Return the fan's currently SET mode."""
    resource = controller.get(thermostat_id)
    if resource is None:
        return None

    fan_mode_map = {
        pyadc.thermostat.ThermostatFanMode.AUTO: FAN_AUTO,
        pyadc.thermostat.ThermostatFanMode.ON: FAN_ON,
        pyadc.thermostat.ThermostatFanMode.CIRCULATE: FAN_CIRCULATE,
    }

    return fan_mode_map.get(resource.fan_mode)


@callback
def fan_modes_fn(
    controller: pyadc.ThermostatController, thermostat_id: str
) -> list[str]:
    """Return the SUPPORTED fan modes."""
    resource = controller.get(thermostat_id)
    if resource is None:
        return []

    modes = []
    if resource.attributes.supports_fan_mode:
        modes.append(FAN_AUTO)
        modes.append(FAN_ON)

    if (
        resource.attributes.supports_circulate_fan_mode_always
        or resource.attributes.supports_circulate_fan_mode_when_off
    ):
        modes.append(FAN_CIRCULATE)

    return modes


@callback
def supported_features_fn(
    controller: pyadc.ThermostatController, thermostat_id: str
) -> ClimateEntityFeature:
    """Return the supported features for the thermostat."""
    resource = controller.get(thermostat_id)

    if resource is None:
        return ClimateEntityFeature(0)

    features = ClimateEntityFeature.TURN_OFF

    if resource.attributes.supports_heat_mode or resource.attributes.supports_cool_mode:
        features |= ClimateEntityFeature.TARGET_TEMPERATURE

    if resource.attributes.supports_auto_mode:
        features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

    # if resource.attributes.supports_humidity:
    #     features |= ClimateEntityFeature.TARGET_HUMIDITY

    if resource.attributes.supports_fan_mode:
        features |= ClimateEntityFeature.FAN_MODE

    return features


@callback
def hvac_mode_fn(
    controller: pyadc.ThermostatController, thermostat_id: str
) -> HVACMode | None:
    """Return the current HVAC mode."""
    resource = controller.get(thermostat_id)
    if resource is None:
        return None

    state = resource.attributes.state
    if state == pyadc.thermostat.ThermostatState.OFF:
        return HVACMode.OFF
    if state == pyadc.thermostat.ThermostatState.HEAT:
        return HVACMode.HEAT
    if state == pyadc.thermostat.ThermostatState.COOL:
        return HVACMode.COOL
    if state == pyadc.thermostat.ThermostatState.AUTO:
        return HVACMode.HEAT_COOL
    if (
        resource.attributes.schedule_mode
        != pyadc.thermostat.ThermostatScheduleMode.MANUAL_MODE
    ):
        return HVACMode.AUTO
    return None


@callback
def hvac_modes_fn(
    controller: pyadc.ThermostatController, thermostat_id: str
) -> list[HVACMode]:
    """Return supported HVAC modes."""
    resource = controller.get(thermostat_id)
    if resource is None:
        return []

    modes = []
    # AUXHEAT
    if resource.attributes.supports_off_mode:
        modes.append(HVACMode.OFF)
    if resource.attributes.supports_heat_mode:
        modes.append(HVACMode.HEAT)
    if resource.attributes.supports_cool_mode:
        modes.append(HVACMode.COOL)
    if resource.attributes.supports_auto_mode:
        modes.append(HVACMode.HEAT_COOL)
    if resource.attributes.supports_schedules:
        modes.append(HVACMode.AUTO)
    # if resource.attributes.supports_fan_mode:
    #     modes.append(HVACMode.FAN_ONLY)
    return modes


@callback
def target_temperature_fn(
    controller: pyadc.ThermostatController, thermostat_id: str
) -> float | None:
    """Return the target heat and cool temperatures."""
    resource = controller.get(thermostat_id)
    if (
        resource is None
        or resource.attributes.state == pyadc.thermostat.ThermostatState.OFF
    ):
        return None

    # If the temperature is in HEAT mode, return the heat setpoint.
    # If it's in COOL mode, return the cool setpoint.
    # If it's in AUTO mode, use inferred state to determine which setpoint to return.
    if resource.attributes.state in [
        pyadc.thermostat.ThermostatState.HEAT,
        pyadc.thermostat.ThermostatState.AUXHEAT,
    ] or (
        resource.attributes.state == pyadc.thermostat.ThermostatState.AUTO
        and resource.attributes.inferred_state == pyadc.thermostat.ThermostatState.HEAT
    ):
        return resource.attributes.heat_setpoint
    if resource.attributes.state == pyadc.thermostat.ThermostatState.COOL or (
        resource.attributes.state == pyadc.thermostat.ThermostatState.AUTO
        and resource.attributes.inferred_state == pyadc.thermostat.ThermostatState.COOL
    ):
        return resource.attributes.cool_setpoint

    return None


@callback
def target_temperature_high_fn(
    controller: pyadc.ThermostatController, thermostat_id: str
) -> float | None:
    """Return the target high temperature."""
    resource = controller.get(thermostat_id)
    if (
        resource is None
        or resource.attributes.state == pyadc.thermostat.ThermostatState.OFF
    ):
        return None

    return resource.attributes.cool_setpoint


@callback
def target_temperature_low_fn(
    controller: pyadc.ThermostatController, thermostat_id: str
) -> float | None:
    """Return the target low temperature."""
    resource = controller.get(thermostat_id)
    if (
        resource is None
        or resource.attributes.state == pyadc.thermostat.ThermostatState.OFF
    ):
        return None

    return resource.attributes.heat_setpoint


@callback
def uses_celsius_fn(controller: pyadc.ThermostatController, thermostat_id: str) -> bool:
    """Return if the thermostat uses Celsius."""
    resource = controller.get(thermostat_id)
    if resource is None:
        return False

    return resource.attributes.uses_celsius


@callback
def target_temperature_step_fn(
    controller: pyadc.ThermostatController, thermostat_id: str
) -> float | None:
    """Return the target temperature step size."""
    resource = controller.get(thermostat_id)
    if resource is None:
        return None

    return resource.attributes.setpoint_offset


# Functions for turning off, setting hvac mode, preset mode, fan mode, humidity, and temperature.
@callback
async def turn_off_fn(
    controller: pyadc.ThermostatController, thermostat_id: str
) -> None:
    """Turn off the thermostat."""
    await controller.set_state(
        thermostat_id, state=pyadc.thermostat.ThermostatState.OFF
    )


@callback
async def set_hvac_mode_fn(
    controller: pyadc.ThermostatController,
    thermostat_id: str,
    hvac_mode: HVACMode,
) -> None:
    """Set the HVAC mode."""

    state_map = {
        HVACMode.OFF: pyadc.thermostat.ThermostatState.OFF,
        HVACMode.HEAT: pyadc.thermostat.ThermostatState.HEAT,
        HVACMode.COOL: pyadc.thermostat.ThermostatState.COOL,
        HVACMode.HEAT_COOL: pyadc.thermostat.ThermostatState.AUTO,
    }

    if requested_hvac_mode := state_map.get(hvac_mode):
        await controller.set_state(thermostat_id, state=requested_hvac_mode)


@callback
async def set_fan_mode_fn(
    controller: pyadc.ThermostatController,
    thermostat_id: str,
    fan_mode: str,
) -> None:
    """Set the fan mode."""
    fan_mode_map = {
        FAN_AUTO: pyadc.thermostat.ThermostatFanMode.AUTO,
        FAN_ON: pyadc.thermostat.ThermostatFanMode.ON,
        FAN_CIRCULATE: pyadc.thermostat.ThermostatFanMode.CIRCULATE,
    }

    if requested_fan_mode := fan_mode_map.get(fan_mode):
        await controller.set_state(
            thermostat_id, fan_mode=requested_fan_mode, fan_mode_duration=0
        )


# @callback
# async def set_humidity_fn(
#     controller: pyadc.ThermostatController,
#     thermostat_id: str,
#     humidity: int,
# ) -> None:
#     """Set the humidity."""
#     await controller.set_state(thermostat_id, humidity=humidity)


@callback
async def set_temperature_fn(
    controller: pyadc.ThermostatController,
    thermostat_id: str,
    target_temp: float | None = None,
    current_hvac_mode: HVACMode | None = None,
    target_temp_high: float | None = None,
    target_temp_low: float | None = None,
) -> None:
    """Set the target temperature."""

    if target_temp_high and target_temp_low:
        await controller.set_state(thermostat_id, heat_setpoint=target_temp_low)
        await controller.set_state(thermostat_id, cool_setpoint=target_temp_high)
    elif target_temp and current_hvac_mode:
        if current_hvac_mode == HVACMode.HEAT:
            await controller.set_state(thermostat_id, heat_setpoint=target_temp)
        elif current_hvac_mode == HVACMode.COOL:
            await controller.set_state(thermostat_id, cool_setpoint=target_temp)


@dataclass(frozen=True, kw_only=True)
class AdcClimateEntityDescription(
    Generic[AdcManagedDeviceT, AdcControllerT],
    AdcEntityDescription[AdcManagedDeviceT, AdcControllerT],
    ClimateEntityDescription,
):
    """Base Alarm.com thermostat entity description."""

    hvac_mode_fn: Callable[[AdcControllerT, str], HVACMode | None]
    """Return the current HVAC mode."""
    temperature_fn: Callable[[AdcControllerT, str], float | None]
    """Return the current temperature."""
    target_temperature_fn: Callable[[AdcControllerT, str], float | None]
    """Return the target heat and cool temperatures."""
    supported_features_fn: Callable[[AdcControllerT, str], ClimateEntityFeature]
    """Return the supported features for the thermostat."""
    hvac_modes_fn: Callable[[AdcControllerT, str], list[HVACMode]]
    """Return supported HVAC modes."""
    fan_mode_fn: Callable[[AdcControllerT, str], str | None]
    """Return the fan's currently SET mode."""
    fan_modes_fn: Callable[[AdcControllerT, str], list[str]]
    """Return the SUPPORTED fan modes."""
    current_humidity_fn: Callable[[AdcControllerT, str], int | None]
    """Return the current humidity."""
    target_temperature_high_fn: Callable[[AdcControllerT, str], float | None]
    """Return the target high temperature."""
    target_temperature_low_fn: Callable[[AdcControllerT, str], float | None]
    """Return the target low temperature."""
    uses_celsius_fn: Callable[[AdcControllerT, str], bool]
    """Return if the thermostat uses Celsius."""
    target_temperature_step_fn: Callable[[AdcControllerT, str], float | None]
    """Return the target temperature step size."""
    turn_off_fn: Callable[[AdcControllerT, str], Coroutine[Any, Any, None]]
    """Turn off the thermostat."""
    set_hvac_mode_fn: Callable[
        [AdcControllerT, str, HVACMode], Coroutine[Any, Any, None]
    ]
    """Set the HVAC mode."""
    set_fan_mode_fn: Callable[[AdcControllerT, str, str], Coroutine[Any, Any, None]]
    """Set the fan mode."""
    # set_humidity_fn: Callable[[AdcControllerT, str, int], Coroutine[Any, Any, None]]
    # """Set the humidity."""
    set_temperature_fn: Callable[
        [
            AdcControllerT,
            str,
            float | None,
            HVACMode | None,
            float | None,
            float | None,
        ],
        Coroutine[Any, Any, None],
    ]
    """Set the target temperature."""


ENTITY_DESCRIPTIONS: list[
    AdcClimateEntityDescription[pyadc.thermostat.Thermostat, pyadc.ThermostatController]
] = [
    AdcClimateEntityDescription(
        key="thermostats",
        controller_fn=lambda hub, _: hub.api.thermostats,
        hvac_mode_fn=hvac_mode_fn,
        temperature_fn=current_temperature_fn,
        target_temperature_fn=target_temperature_fn,
        supported_features_fn=supported_features_fn,
        hvac_modes_fn=hvac_modes_fn,
        fan_mode_fn=fan_mode_fn,
        fan_modes_fn=fan_modes_fn,
        current_humidity_fn=current_humidity_fn,
        target_temperature_high_fn=target_temperature_high_fn,
        target_temperature_low_fn=target_temperature_low_fn,
        uses_celsius_fn=uses_celsius_fn,
        target_temperature_step_fn=target_temperature_step_fn,
        turn_off_fn=turn_off_fn,
        set_hvac_mode_fn=set_hvac_mode_fn,
        set_fan_mode_fn=set_fan_mode_fn,
        # set_humidity_fn=set_humidity_fn,
        set_temperature_fn=set_temperature_fn,
    )
]


class AdcClimateEntity(AdcEntity[AdcManagedDeviceT, AdcControllerT], ClimateEntity):
    """Base Alarm.com thermostat entity."""

    entity_description: AdcClimateEntityDescription

    @callback
    def initiate_state(self) -> None:
        """Initiate entity state."""

        # fmt: off
        self._attr_hvac_mode = self.entity_description.hvac_mode_fn(self.controller, self.resource_id)
        self._attr_current_temperature = self.entity_description.temperature_fn(self.controller, self.resource_id)
        self._attr_fan_mode = self.entity_description.fan_mode_fn(self.controller, self.resource_id)
        self._attr_fan_modes = self.entity_description.fan_modes_fn(self.controller, self.resource_id)
        self._attr_current_humidity = self.entity_description.current_humidity_fn(self.controller, self.resource_id)
        self._attr_target_temperature_low = self.entity_description.target_temperature_low_fn(self.controller, self.resource_id)
        self._attr_target_temperature_high = self.entity_description.target_temperature_high_fn(self.controller, self.resource_id)
        self._attr_target_temperature = self.entity_description.target_temperature_fn(self.controller, self.resource_id)
        self._attr_supported_features = self.entity_description.supported_features_fn(self.controller, self.resource_id)
        self._attr_hvac_modes = self.entity_description.hvac_modes_fn(self.controller, self.resource_id)
        self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT if not self.entity_description.uses_celsius_fn(self.controller, self.resource_id) else UnitOfTemperature.CELSIUS
        self._attr_target_temperature_step = self.entity_description.target_temperature_step_fn(self.controller, self.resource_id)
        # fmt: off

        super().initiate_state()

    @callback
    def update_state(self, message: pyadc.EventBrokerMessage | None = None) -> None:
        """Update entity state."""

        if isinstance(message, pyadc.ResourceEventMessage):
            # fmt: off
            self._attr_hvac_mode = self.entity_description.hvac_mode_fn(self.controller, self.resource_id)
            self._attr_current_temperature = self.entity_description.temperature_fn(self.controller, self.resource_id)
            self._attr_fan_mode = self.entity_description.fan_mode_fn(self.controller, self.resource_id)
            self._attr_fan_modes = self.entity_description.fan_modes_fn(self.controller, self.resource_id)
            self._attr_current_humidity = self.entity_description.current_humidity_fn(self.controller, self.resource_id)
            self._attr_target_temperature_high = self.entity_description.target_temperature_high_fn(self.controller, self.resource_id)
            self._attr_target_temperature_low = self.entity_description.target_temperature_low_fn(self.controller, self.resource_id)
            self._attr_target_temperature = self.entity_description.target_temperature_fn(self.controller, self.resource_id)
            # fmt: on

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        await self.entity_description.set_hvac_mode_fn(
            self.controller, self.resource_id, hvac_mode
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        await self.entity_description.set_fan_mode_fn(
            self.controller, self.resource_id, fan_mode
        )

    # async def async_set_humidity(self, humidity: int) -> None:
    #     """Set the humidity."""
    #     await self.entity_description.set_humidity_fn(
    #         self.controller, self.resource_id, humidity
    #     )

    async def async_turn_off(self) -> None:
        """Turn off the thermostat."""
        await self.entity_description.turn_off_fn(self.controller, self.resource_id)

    async def async_set_temperature(
        self,
        **kwargs: Any,
    ) -> None:
        """Set the target temperature."""
        await self.entity_description.set_temperature_fn(
            self.controller,
            self.resource_id,
            kwargs.get("target_temp"),
            self.hvac_mode,
            kwargs.get("target_temp_high"),
            kwargs.get("target_temp_low"),
        )
