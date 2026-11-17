"""Alarm.com model for trouble conditions."""

from dataclasses import dataclass, field
from enum import Enum

from _pyalarmdotcomajax.models.base import (
    AdcResource,
    AdcResourceAttributes,
    ResourceType,
)


class TroubleConditionSeverity(Enum):
    """Severity of trouble condition."""

    UNKNOWN = 0
    ALARM = 1
    ISSUE = 2


class TroubleConditionSubtype(Enum):
    """Subtypes for trouble conditions."""

    UNKNOWN = -1

    NoSubType = 0
    SensorMalfunction_GeoServices = 1
    SensorMalfunction_LiftMaster = 2
    SensorMalfunction_ZWave = 3
    SensorMalfunction_Lutron = 4
    SensorMalfunction_Sensor = 5
    SensorMalfunction_Sonos = 6
    SensorMalfunction_CarConnector = 7
    IncompatibleDevice_ADCSmartThermostat = 8
    IncompatibleDevice_ImageSensor = 9
    IncompatibleDevice_Kwikset = 10
    IncompatibleDevice_Quickbox = 11
    IncompatibleDevice_RemoteTemperatureSensor = 12
    IncompatibleDevice_Schlage = 13
    IncompatibleDevice_Stelpro = 14
    IncompatibleDevice_TwoWayTalkingTouchScreen = 15
    IncompatibleDevice_Westinghouse = 16
    IncompatibleDevice_Yale = 17
    IncompatibleDevice_ZWaveGarage = 18
    SensorLowBattery_CarConnector = 19
    SensorTamper_CarConnector = 20
    SensorTamper_ContactSensor = 21
    SensorTamper_MotionSensor = 22
    SensorTamper_ImageSensor = 23
    ControllerPowerFault_Aero = 24
    ControllerPowerFault_Mercury = 25
    PanelTamper_AlarmHub = 26
    SecureEnrollmentFailed_Critical = 27
    SensorMalfunction_AccessPoint = 28
    IncompatibleDevice_IQLinearGarage = 29
    IncompatiblePanelVersion_IQWifi6 = 30
    SensorLowBattery_RechargeableVideoDevice = 31
    SensorLowBattery_CriticalRechargeableVideoDevice = 32
    BroadbandCommFailure_GunshotSensor = 33
    CellCommFailure_GunshotSensor = 34
    CameraUnexpectedlyNotRecording_SVR = 35
    CameraUnexpectedlyNotRecording_Onboard = 36
    CameraUnexpectedlyNotRecording_SVRAndOnboard = 37

    @classmethod
    def _missing_(cls: type, value: object) -> Enum:
        """Set default enum member if an unknown value is provided."""
        return TroubleConditionSubtype.UNKNOWN


class TroubleConditionType(Enum):
    """Types of trouble conditions."""

    UNKNOWN = -1

    SensorMalfunction = 12
    ACFailure = 14
    SensorLowBattery = 15
    PanelLowBattery = 16
    PanelNotResponding = 17
    CameraNotReachable = 21
    WaterAlert = 50
    AlarmInMemory = 53
    SmokeSensorReset = 57
    BatteryCharging = 69
    SmallLeak = 95
    MediumLeak = 96
    LargeLeak = 97
    SevereHVACAlert = 108
    VideoDeviceHighTemperatureCutoff = 176
    VideoDeviceLowTemperatureCutoff = 177
    VideoDeviceLowVoltageShutdown = 178
    SensorNotResponding = 190
    VideoDeviceLowBatteryAndLowTemperatureAlert = 206

    @classmethod
    def _missing_(cls: type, value: object) -> Enum:
        """Set default enum member if an unknown value is provided."""
        return TroubleConditionType.UNKNOWN


@dataclass
class TroubleConditionAttributes(AdcResourceAttributes):
    """Attributes of trouble condition."""

    # description: str
    severity: TroubleConditionSeverity | None = field(default=None)
    trouble_condition_type: TroubleConditionType | None = field(default=None)
    trouble_condition_sub_type: TroubleConditionSubtype | None = field(default=None)
    device_id: int | None = field(default=None)
    ember_device_id: str | None = field(default=None)
    can_be_muted_or_reset: bool | None = field(default=None)

    # sinceUtc: str


@dataclass
class TroubleCondition(AdcResource[TroubleConditionAttributes]):
    """Trouble condition resource."""

    resource_type = ResourceType.TROUBLE_CONDITION
    attributes_type = TroubleConditionAttributes
