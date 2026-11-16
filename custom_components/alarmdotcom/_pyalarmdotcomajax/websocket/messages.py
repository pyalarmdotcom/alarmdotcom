"""Base models for WebSocket messages."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from _pyalarmdotcomajax.models.jsonapi import JsonApiBaseElement
from mashumaro import field_options

UNDEFINED = "**UNDEFINED**"


class ResourcePropertyChangeType(Enum):
    """Enum for property change message types."""

    # Supported
    AmbientTemperature = 1  # Expressed as 100ths of a degree F
    HeatSetPoint = 2  # Expressed as 100ths of a degree F
    CoolSetPoint = 3  # Expressed as 100ths of a degree F
    LightColor = 4

    # Unsupported
    IrrigationStatus = 5

    UNKNOWN = -1

    @classmethod
    def _missing_(cls: type, value: object) -> "ResourcePropertyChangeType":
        """
        Set default enum member if an unknown value is provided.

        Without this, an unmapped property subtype raises ValueError inside
        mashumaro and the event processor drops the whole message (#94:
        "7 is not a valid ResourcePropertyChangeType"). ResourceEventType has
        had this fallback all along.
        """
        return ResourcePropertyChangeType.UNKNOWN


class ResourceEventType(Enum):
    """Enum for event types."""

    # Supported
    ArmedAway = 10
    ArmedNight = 113
    ArmedStay = 9
    Closed = 0
    Disarmed = 8
    DoorLeftOpenRestoral = 103  # When door is closed after being left open.
    DoorLocked = 91
    DoorUnlocked = 90
    ImageSensorUpload = 99
    LightTurnedOff = 316
    LightTurnedOn = 315
    Opened = 15
    OpenedClosed = 100
    SwitchLevelChanged = 317
    ThermostatFanModeChanged = 120
    ThermostatModeChanged = 95
    ThermostatOffset = 105
    ThermostatSetPointChanged = 94

    # Unsupported
    Alarm = 1
    AccessControlDoorAccessGranted = 298
    AlarmCancelled = 238
    ArmingSupervisionFault = 48
    AuxiliaryPanic = 17
    AuxPanicPendingAlarm = 61
    AuxPanicSuspectedAlarm = 65
    BadLockUserCode = 93
    Bypassed = 13
    CommercialClosedOnTime = 127
    CommercialClosedUnexpectedly = 177
    CommercialEarlyClose = 125
    CommercialEarlyOpen = 122
    CommercialLateClose = 126
    CommercialLateOpen = 123
    CommercialOpenOnTime = 124
    DisarmingSupervisionFault = 47
    DoorAccessed = 92
    DoorAccessedDoubleSwipe = 236
    DoorBuzzedFromWebsite = 182
    DoorFailedAccess = 180
    DoorForcedOpen = 181
    DoorHeldOpen = 184
    EndOfBypass = 35
    ExitButtonPressed = 141
    FirePanic = 24
    GoogleSdmEvent = 346
    InAppAuxiliaryPanic = 201
    InAppFirePanic = 200
    InAppPolicePanic = 202
    InAppSilentPolicePanic = 203
    NetworkDhcpReservationsUpdated = 433
    NetworkDhcpSettingsUpdated = 432
    NetworkMapUpdated = 391
    NetworkPortForwardingUpdated = 434
    PackageDeliveryAlert = 363
    PackageRetrievalAlert = 364
    PendingAlarm = 62
    PolicePanic = 22
    PolicePanicSuspectedAlarm = 64
    RouterHostsUpdated = 450
    RouterProfilesUpdated = 451
    SilentPolicePanic = 73
    SilentPolicePanicSuspectedAlarm = 172
    SpeedTestResultsUpdated = 454
    SumpPumpAlertCriticalIssueMalfunction = 118
    SumpPumpAlertCriticalIssueOff = 117
    SumpPumpAlertIdle = 114
    SumpPumpAlertNormalOperation = 115
    SumpPumpAlertPossibleIssue = 116
    Tamper = 7
    UnknownCardFormatRead = 185
    VideoAnalyticsDetection = 210
    VideoEventTriggered = 76
    ViewedByCentralStation = 158
    WrongPinCode = 398

    VideoCameraTriggered = 71  # Person Detected? Package Detected?
    VideoAnalytics2Detection = 302  # Motion

    # Undocumented
    UserLoggedIn = 55
    DoorLeftOpen = 101  # When door is left open for 30 minutes.

    UNKNOWN = -1

    @classmethod
    def _missing_(cls: type, value: object) -> "ResourceEventType":
        """Set default enum member if an unknown value is provided."""
        return ResourceEventType.UNKNOWN


@dataclass(kw_only=True)
class WebSocketMessageTester(JsonApiBaseElement):
    """Universal WebSocket message dataclass to type and build message."""

    event_type: Any = field(default=UNDEFINED)
    event_value: Any = field(default=UNDEFINED)
    event_date_utc: Any = field(default=UNDEFINED)
    qstring_for_extra_data: Any = field(default=UNDEFINED)
    correlated_id: Any = field(
        default=UNDEFINED
    )  # In webapp as correlatedEventId, but in API as correlatedId
    property_: Any = field(default=UNDEFINED, metadata=field_options(alias="property"))
    property_value: Any = field(default=UNDEFINED)
    fence_id: Any = field(default=UNDEFINED)
    is_inside_now: Any = field(default=UNDEFINED)
    new_state: Any = field(default=UNDEFINED)
    flag_mask: Any = field(default=UNDEFINED)


@dataclass
class BaseWSMessage(JsonApiBaseElement):
    """Base alarm.com websocket message."""

    unit_id: str  # Full device ID prefix
    device_id: int  # Full device ID suffix

    full_device_id: str = field(
        init=False
    )  # Full device ID (calculated in __post_init__)

    def __post_init__(self) -> None:
        """Post init hook."""

        self.full_device_id = f"{self.unit_id}-{self.device_id}"


@dataclass
class EventWSMessage(BaseWSMessage):
    """Alarm.com event websocket message."""

    event_date_utc: datetime
    subtype: ResourceEventType = field(metadata=field_options(alias="event_type"))
    value: float | None = field(metadata=field_options(alias="event_value"))
    subvalue: str = field(metadata=field_options(alias="qstring_for_extra_data"))


@dataclass
class MonitoringEventWSMessage(BaseWSMessage):
    """Alarm.com monitoring event websocket message."""

    # Alarm.com's webapp ignores this message type, instead handling monitoring events via event messages.
    # This message type appears to be the only endpoint for ImageSensorUpload events, even though
    # they're ignored by the webapp.

    event_date_utc: datetime
    subtype: ResourceEventType = field(metadata=field_options(alias="event_type"))
    subvalue: str = field(metadata=field_options(alias="correlated_id"))


@dataclass
class PropertyChangeWSMessage(BaseWSMessage):
    """Alarm.com property change websocket message."""

    subtype: ResourcePropertyChangeType = field(
        metadata=field_options(alias="property")
    )
    value: int = field(metadata=field_options(alias="property_value"))


@dataclass
class StatusUpdateWSMessage(BaseWSMessage):
    """Alarm.com property change websocket message."""

    # Alarm.com's webapp doesn't seem to use this message type. Status updates are handled via event messages.

    value: int = field(metadata=field_options(alias="new_state"))
    subvalue: int = field(metadata=field_options(alias="flag_mask"))


@dataclass
class GeofenceCrossingWSMessage(BaseWSMessage):
    """Alarm.com property change websocket message."""

    # Alarm.com's webapp doesn't seem to use this message type. Geofence crossings are handled via event messages.

    value: int = field(metadata=field_options(alias="fence_id"))
    subvalue: int = field(metadata=field_options(alias="is_inside_now"))
