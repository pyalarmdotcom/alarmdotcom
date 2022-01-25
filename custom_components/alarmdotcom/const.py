"""Const for the Alarmdotcom integration."""

from __future__ import annotations

from enum import Enum
from types import FunctionType
from typing import TypedDict

from typing_extensions import NotRequired

from pyalarmdotcomajax.const import ArmingOption as ADCArmingOption

INTEGRATION_NAME = "Alarm.com"
DOMAIN = "alarmdotcom"
ISSUE_URL = ""
STARTUP_MESSAGE = f"""
===================================================================
{DOMAIN}
This is a custom component
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
===================================================================
"""

STATE_MALFUNCTION = "Malfunction"

# Attributes
ATTR_CLIENT = "client"
ATTR_COORDINATOR = "coordinator"

# Storage
STORE_CONTROLLER = "controller"

# ADC Binary Sensor Types
ADC_BINARY_TYPE_UNKNOWN = "generic_sensor"
ADC_BINARY_TYPE_CONTACT = "contact_sensor"
ADC_BINARY_TYPE_SMOKE = "smoke_sensor"
ADC_BINARY_TYPE_CO = "co_sensor"
ADC_BINARY_TYPE_PANIC = "panic_sensor"
ADC_BINARY_TYPE_GLASS = "glass_sensor"

# #
# CONFIGURATION
# #

# Configuration
CONF_USERNAME = "username"
CONF_PASSWORD = "password"  # nosec
CONF_2FA_COOKIE = "2fa_cookie"

CONF_FORCE_BYPASS = "force_bypass"
CONF_NO_DELAY = "no_entry_delay"
CONF_SILENT_ARM = "silent_arming"
CONF_ARM_CODE = "arm_code"

# Legacy configuration.yaml
LEGACY_CONF_FORCE_BYPASS = "force_bypass"
LEGACY_CONF_NO_ENTRY_DELAY = "no_entry_delay"
LEGACY_CONF_SILENT_ARMING = "silent_arming"
LEGACY_CONF_TWO_FACTOR_COOKIE = "two_factor_cookie"

# #
# Device States
# #


class ADCIArmingOption(Enum):
    """Possible selections for arming options (force bypass, etc.)."""

    ALWAYS = "Always"
    NEVER = "Never"
    STAY = "Stay Only"
    AWAY = "Away Only"

    @property
    def to_adc(self) -> ADCArmingOption:
        """Return pyalarmdotcomajax enum for selected arming option."""
        lookup = {
            ADCIArmingOption.STAY: ADCArmingOption.STAY,
            ADCIArmingOption.AWAY: ADCArmingOption.AWAY,
            ADCIArmingOption.NEVER: ADCArmingOption.NEVER,
            ADCIArmingOption.ALWAYS: ADCArmingOption.ALWAYS,
        }

        return lookup[self]

    @classmethod
    def from_adc(cls, adc_enum: ADCArmingOption) -> ADCIArmingOption:
        """Return alarmdotcom enum for supplied pyalarmdotcomajax enum."""
        lookup = {
            ADCArmingOption.STAY: ADCIArmingOption.STAY,
            ADCArmingOption.AWAY: ADCIArmingOption.AWAY,
            ADCArmingOption.NEVER: ADCIArmingOption.NEVER,
            ADCArmingOption.ALWAYS: ADCIArmingOption.ALWAYS,
        }

        return lookup[adc_enum]

    @classmethod
    def from_config_yaml(cls, legacy_value: str) -> ADCIArmingOption:
        """Return alarmdotcom enum for supplied pyalarmdotcomajax enum."""
        lookup = {
            "home": ADCIArmingOption.STAY,
            "away": ADCIArmingOption.AWAY,
            "false": ADCIArmingOption.NEVER,
            "true": ADCIArmingOption.ALWAYS,
        }

        return lookup[legacy_value]


class ADCIPartitionState(Enum):
    """Enum of arming states."""

    UNKNOWN = "UNKNOWN"
    DISARMED = "DISARMED"
    ARMED_STAY = "ARMED_STAY"
    ARMED_AWAY = "ARMED_AWAY"
    ARMED_NIGHT = "ARMED_NIGHT"


class ADCILockState(Enum):
    """Enum of lock states."""

    FAILED = "FAILED"
    LOCKED = "LOCKED"
    UNLOCKED = "UNLOCKED"


class ADCISensorState(Enum):
    """Enum of sensor states."""

    UNKNOWN = "UNKNOWN"
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    DRY = "DRY"
    WET = "WET"


class ADCIGarageDoorState(Enum):
    """Enum of garage door states."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


# #
# Device Data Dictionaries
# #


class ADCIBaseEntity(TypedDict):
    """Base dict for an ADCI entity."""

    unique_id: str
    name: str
    identifiers: NotRequired[list]
    battery_low: NotRequired[bool]
    malfunction: NotRequired[bool]
    mac_address: NotRequired[str]


class ADCISystemData(ADCIBaseEntity):
    """Dict for an ADCI system."""

    unit_id: str


class ADCIPartitionData(ADCIBaseEntity):
    """Dict for an ADCI partition."""

    make_and_model: NotRequired[dict]
    uncleared_issues: bool
    desired_state: Enum
    raw_state_text: str
    system_id: NotRequired[str]
    state: ADCIPartitionState
    parent_id: str

    async_disarm_callback: FunctionType
    async_arm_stay_callback: FunctionType
    async_arm_away_callback: FunctionType
    async_arm_night_callback: FunctionType


class ADCISensorData(ADCIBaseEntity):
    """Dict for an ADCI sensor."""

    make_and_model: NotRequired[dict]
    device_subtype: NotRequired[Enum]
    partition_id: NotRequired[str]
    raw_state_text: NotRequired[str]
    state: ADCISensorState | bool | None
    parent_id: str


class ADCILockData(ADCIBaseEntity):
    """Dict for an ADCI Lock."""

    make_and_model: NotRequired[dict]
    desired_state: Enum
    raw_state_text: str
    state: ADCILockState
    parent_id: str

    async_lock_callback: FunctionType
    async_unlock_callback: FunctionType


class ADCIGarageDoorData(ADCIBaseEntity):
    """Dict for an ADCI garage door."""

    make_and_model: NotRequired[dict]
    desired_state: Enum
    raw_state_text: str
    state: ADCIGarageDoorState
    async_open_callback: FunctionType
    async_close_callback: FunctionType
    parent_id: str


class ADCIEntities(TypedDict):
    """Hold all sensors, panels, etc. belonging to a controller."""

    entity_data: dict[
        str,
        ADCIGarageDoorData
        | ADCISystemData
        | ADCISensorData
        | ADCILockData
        | ADCIPartitionData,
    ]
    system_ids: set[str]
    partition_ids: set[str]
    sensor_ids: set[str]
    lock_ids: set[str]
    garage_door_ids: set[str]
    low_battery_ids: set[str]
    malfunction_ids: set[str]


class ADCIDevices:
    """Define device-related constants."""
