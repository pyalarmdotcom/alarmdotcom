"""Alarm.com model for thermostats."""

from abc import ABC
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Generic, TypeVar

from _pyalarmdotcomajax.models.base import (
    AdcDeviceResource,
    BaseManagedDeviceAttributes,
    ResourceType,
)

# Declared locally rather than imported from _pyalarmdotcomajax.models.base,
# even though it's the same conceptual type variable. Works around a known,
# longstanding mypy limitation (python/mypy#11854): a TypeVar imported from
# another module, used to parameterize a Generic[] class, triggers a spurious
# "Free type variable expected in Generic[...]" error. Bound identically, so
# this stays fully type-compatible with BaseManagedDeviceAttributes[DeviceState]
# (TypeVar bound-checking is structural, not based on object identity).
DeviceState = TypeVar("DeviceState", bound=Enum)


@dataclass(kw_only=True)
class TemperatureDeviceAttributes(BaseManagedDeviceAttributes[DeviceState], Generic[DeviceState], ABC):
    """Attributes of temperature device."""

    # fmt: off
    ambient_temp: float | None = field(metadata={"description": "The current temperature reported by the device."}, default=None)
    has_rts_issue: bool = field(metadata={"description": "Does this device have a Rts issue?"}, default=False)
    is_paired: bool = field(metadata={"description": "Is this device paired to another?"}, default=False)
    supports_humidity: bool = field(metadata={"description": "Whether the device supports humidity."}, default=False)
    humidity_level: int | None = field(metadata={"description": "The current humidity level reported by the device."}, default=None)
    # temp_forwarding_active: bool
    # fmt: on


class ThermostatState(IntEnum):
    """Thermostat states."""

    UNKNOWN = 0
    OFF = 1
    HEAT = 2
    COOL = 3
    AUTO = 4
    AUXHEAT = 5

    @classmethod
    def _missing_(cls: type, value: object) -> "ThermostatState":
        """Set default enum member if an unknown value is provided."""
        return ThermostatState.UNKNOWN


class ThermostatReportedFanMode(IntEnum):
    """Thermostat fan modes as reported in the thermostat response object."""

    AUTO_LOW = 0
    ON_LOW = 1
    AUTO_HIGH = 2
    ON_HIGH = 3
    AUTO_MEDIUM = 4
    ON_MEDIUM = 5
    CIRCULATE = 6
    HUMIDITY = 7

    @classmethod
    def _missing_(cls: type, value: object) -> "ThermostatReportedFanMode":
        """Set default enum member if an unknown value is provided."""
        return ThermostatReportedFanMode.AUTO_LOW


class ThermostatFanMode(IntEnum):
    """User-facing thermostat fan modes."""

    UNKNOWN = -1
    AUTO = 0
    ON = 1
    CIRCULATE = 2

    @classmethod
    def _missing_(cls: type, value: object) -> "ThermostatFanMode":
        """Set default enum member if an unknown value is provided."""
        return ThermostatFanMode.UNKNOWN


class ThermostatScheduleMode(IntEnum):
    """Thermostat schedule modes."""

    MANUAL_MODE = 0
    SCHEDULED = 1
    SMART_SCHEDULES = 2

    @classmethod
    def _missing_(cls: type, value: object) -> "ThermostatScheduleMode":
        """Set default enum member if an unknown value is provided."""
        return ThermostatScheduleMode.MANUAL_MODE


THERMOSTAT_MODELS = {
    4293: {"manufacturer": "Honeywell", "model": "T6 Pro"},
    10023: {"manufacturer": "ecobee", "model": "ecobee3 lite"},
}


@dataclass(kw_only=True)
class ThermostatAttributes(TemperatureDeviceAttributes[ThermostatState]):
    """Attributes of temperature device."""

    desired_state: ThermostatState | None = field(metadata={"description": "Desired device state."}, default=None)
    state: ThermostatState = field(metadata={"description": "Current device state."}, default=ThermostatState.UNKNOWN)

    # fmt: off
    auto_setpoint_buffer: float = field(metadata={"description": "The minimum buffer between the heat and cool setpoints."})
    away_cool_setpoint: float = field(metadata={"description": "The cool setpoint when away."})
    away_heat_setpoint: float = field(metadata={"description": "The heat setpoint when away."})
    cool_setpoint: float = field(metadata={"description": "The current cool setpoint."})
    desired_cool_setpoint: float = field(metadata={"description": "The desired cool setpoint."})
    desired_heat_setpoint: float = field(metadata={"description": "The desired heat setpoint."})
    fan_duration: int | None = field(metadata={"description": "The duration to run the fan. Only used to offset the commands."}, default=None)
    fan_mode: ThermostatReportedFanMode | None = field(default=None, metadata={"description": "The current fan mode."})
    forwarding_ambient_temp: float | None = field(metadata={"description": "The current temperature including any additional temperature sensor averaging."}, default=None)
    has_pending_setpoint_change: bool = field(metadata={"description": "Indicates if there is a pending setpoint change."})
    has_pending_temp_mode_change: bool = field(metadata={"description": "Indicates if there is a pending temperature mode change."})
    heat_setpoint: float = field(metadata={"description": "The current heat setpoint."})
    inferred_state: ThermostatState = field(metadata={"description": "The inferred mode when in auto mode."}, default=ThermostatState.UNKNOWN)
    is_controlled: bool = field(metadata={"description": "Indicates if the thermostat is controlled by another thermostat."})
    is_pool_controller: bool = field(metadata={"description": "Indicates if the thermostat is a pool controller."})
    max_aux_heat_setpoint: float = field(metadata={"description": "The maximum valid aux heat setpoint."})
    max_cool_setpoint: float = field(metadata={"description": "The maximum valid cool setpoint."})
    max_heat_setpoint: float = field(metadata={"description": "The maximum valid heat setpoint."})
    min_aux_heat_setpoint: float = field(metadata={"description": "The minimum valid aux heat setpoint."})
    min_cool_setpoint: float = field(metadata={"description": "The minimum valid cool setpoint."})
    min_heat_setpoint: float = field(metadata={"description": "The minimum valid heat setpoint."})
    requires_setup: bool = field(metadata={"description": "Indicates if the thermostat requires a setup wizard."})
    schedule_mode: ThermostatScheduleMode = field(metadata={"description": "The current schedule mode."})
    setpoint_offset: float = field(metadata={"description": "The amount to increment or decrement the setpoint by."})
    supported_fan_durations: list[int] = field(metadata={"description": "The supported fan mode durations."}, default_factory=list)
    supports_auto_mode: bool = field(metadata={"description": "Indicates if the thermostat supports the auto temperature mode."})
    supports_aux_heat_mode: bool = field(metadata={"description": "Indicates if the thermostat supports the aux heat temperature mode."})
    supports_circulate_fan_mode_always: bool = field(metadata={"description": "Indicates if the thermostat supports the circulate fan mode regardless of temperature mode."})
    supports_circulate_fan_mode_when_off: bool = field(metadata={"description": "Indicates if the thermostat supports the circulate fan mode when in OFF mode."})
    supports_cool_mode: bool = field(metadata={"description": "Indicates if the thermostat supports the cool temperature mode."})
    supports_fan_mode: bool = field(metadata={"description": "Indicates if the thermostat supports fan mode control."})
    supports_heat_mode: bool = field(metadata={"description": "Indicates if the thermostat supports the heat temperature mode."})
    supports_indefinite_fan_on: bool = field(metadata={"description": "Indicates if the thermostat supports running the fan indefinitely."})
    supports_off_mode: bool = field(metadata={"description": "Indicates if the thermostat supports the off temperature mode."})
    supports_schedules: bool = field(metadata={"description": "Indicates if the thermostat supports schedules."})
    supports_setpoints: bool = field(metadata={"description": "Indicates if the thermostat supports setpoints."})
    desired_fan_mode: ThermostatReportedFanMode | None = field(default=None, metadata={"description": "The desired fan mode."})
    # fmt: on

    uses_celsius: bool = field(
        default=False,
        metadata={"description": "Whether the thermostat reports in celsius or fahrenheit."},
    )

    @property
    def has_dirty_setpoint(self) -> bool:
        """Whether the thermostat has a setpoint that is currently being changed."""

        return self.has_pending_setpoint_change or self.has_pending_temp_mode_change



@dataclass
class Thermostat(AdcDeviceResource[ThermostatAttributes]):
    """Thermostat resource."""

    resource_type = ResourceType.THERMOSTAT
    attributes_type = ThermostatAttributes
    resource_models = THERMOSTAT_MODELS

    @property
    def fan_mode(self) -> ThermostatFanMode:
        """The current fan mode."""

        current_fan_mode = (
            self.attributes.desired_fan_mode
            if self.attributes.desired_fan_mode is not None
            else self.attributes.fan_mode
        )

        if current_fan_mode in (
            ThermostatReportedFanMode.AUTO_LOW,
            ThermostatReportedFanMode.AUTO_MEDIUM,
            ThermostatReportedFanMode.AUTO_HIGH,
        ):
            return ThermostatFanMode.AUTO
        if current_fan_mode in (
            ThermostatReportedFanMode.ON_LOW,
            ThermostatReportedFanMode.ON_MEDIUM,
            ThermostatReportedFanMode.ON_HIGH,
        ):
            return ThermostatFanMode.ON
        if current_fan_mode == ThermostatReportedFanMode.CIRCULATE:
            return ThermostatFanMode.CIRCULATE
        return ThermostatFanMode.UNKNOWN

    @property
    def supported_fan_durations(self) -> list[int]:
        """Return allowed fan durations for the current desired mode."""

        if not self.attributes.supported_fan_durations:
            return []

        durations = sorted(set(self.attributes.supported_fan_durations))
        if self.attributes.supports_indefinite_fan_on and 0 not in durations:
            durations.insert(0, 0)
        return durations
