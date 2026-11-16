"""Alarm.com models."""

from __future__ import annotations

import logging
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import ClassVar, Generic, TypeVar

from _pyalarmdotcomajax.models.jsonapi import JsonApiBaseElement, Resource
from _pyalarmdotcomajax.util import get_related_entity_id_by_key
from mashumaro import field_options

log = logging.getLogger(__name__)


class ResourceType(StrEnum):
    """Type of resource."""

    # Devices
    CAMERA = "video/camera"
    GARAGE_DOOR = "devices/garage-door"
    GATE = "devices/gate"
    LIGHT = "devices/light"
    LOCK = "devices/lock"
    PARTITION = "devices/partition"
    SENSOR = "devices/sensor"
    SYSTEM = "systems/system"
    THERMOSTAT = "devices/thermostat"
    WATER_SENSOR = "devices/water-sensor"
    SWITCH = "devices/switch"
    WATER_VALVE = "devices/water-valve"

    IMAGE_SENSOR = "image-sensor/image-sensor"
    IMAGE_SENSOR_IMAGE = "image-sensor/image-sensor-image"

    # Meta
    AVAILABLE_SYSTEM = "systems/availableSystemItem"
    IDENTITY = "identity"
    DEALER = "dealers/dealer"
    PROFILE = "profile/profile"
    TWO_FACTOR = "twoFactorAuthentication/twoFactorAuthentication"
    TROUBLE_CONDITION = "troubleConditions/trouble-condition"
    DEVICE_CATALOG = "settings/manage-devices/device-catalog"
    HISTORY_EVENT = "activity/history-event"

    UNKNOWN = "unknown"

    # UNSUPPORTED
    # ACCESS_CONTROL = "devices/access-control-access-point-device"
    # CAMERA_SD = "video/sd-card-camera"
    # CAR_MONITOR = "devices/car-monitor"
    # COMMERCIAL_TEMP = "devices/commercial-temperature-sensor"
    # GEO_DEVICE = "geolocation/geo-device"
    # IQ_ROUTER = "devices/iq-router"
    # REMOTE_TEMP = "devices/remote-temperature-sensor"
    # SCENE = "automation/scene"
    # SHADE = "devices/shade"
    # SMART_CHIME = "devices/smart-chime-device"
    # SUMP_PUMP = "devices/sump-pump"
    # VALVE_SWITCH = "valve-switch"
    # WATER_METER = "devices/water-meter"
    # X10_LIGHT = "devices/x10-light"

    @classmethod
    def _missing_(cls: type, value: object) -> ResourceType:
        """Set default enum member if an unknown value is provided."""
        return ResourceType.UNKNOWN


#
# RESOURCES
#


@dataclass(kw_only=True)
class AdcResourceAttributes(ABC, JsonApiBaseElement):
    """Represents an Alarm.com resource."""

    description: str = field(metadata={"description": "Device name"}, default="")


class AdcResourceSubtype(Enum):
    """Represents Alarm.com resource subtypes."""


AdcResourceAttributesT = TypeVar("AdcResourceAttributesT", bound=AdcResourceAttributes)
AdcManagedDeviceAttributesT = TypeVar("AdcManagedDeviceAttributesT", bound="BaseManagedDeviceAttributes")
AdcResourceSubtypesT = TypeVar("AdcResourceSubtypesT", bound=AdcResourceSubtype)


@dataclass
class AdcResource(Generic[AdcResourceAttributesT]):
    """
    Base class for all Alarm.com resource (device, identity, etc.).

    Accepts a JSON:API resource object. Casts dict of attributes into a dataclass.
    """

    api_resource: Resource = field(repr=False)

    resource_type: ResourceType = field(init=False)
    attributes_type: type[AdcResourceAttributesT] = field(init=False, repr=False)

    id: str = field(init=False)
    attributes: AdcResourceAttributesT = field(init=False)

    def __post_init__(self) -> None:
        """Initialize the resource."""

        self.id = self.api_resource.id
        self.attributes: AdcResourceAttributesT = self.attributes_type.from_dict(self.api_resource.attributes)


@dataclass
class AdcDeviceResource(AdcResource[AdcResourceAttributesT]):
    """Base class for Alarm.com device resource."""

    attributes: AdcResourceAttributesT = field(init=False)

    system_id: str | None = field(init=False)
    model: str | None = field(init=False)

    has_related_system: ClassVar[bool] = True

    def __post_init__(self) -> None:
        """Initialize the resource."""

        super().__post_init__()

        if self.has_related_system:
            self.system_id = get_related_entity_id_by_key(self.api_resource, "system")

        # self.extension_attributes: list[ExtensionAttributes] = []

    @property
    def name(self) -> str:
        """Name of the device."""

        return self.attributes.description


@dataclass
class AdcManagedDeviceResource(AdcDeviceResource[AdcManagedDeviceAttributesT]):
    """Base managed device resource."""

    attributes: AdcManagedDeviceAttributesT = field(init=False)

    # Mapping of model IDs to device manufacturer / model for device type.
    # deviceModelId: {"manufacturer": str, "model": str}
    resource_models: dict[int, dict[str, str]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the resource."""

        super().__post_init__()
        # Set device model
        self.model = None
        if hasattr(self, "resource_models"):
            if hasattr(self.attributes, "device_model") and self.attributes.device_model:
                self.model = str(self.attributes.device_model)
            elif hasattr(self.attributes, "device_model_id") and self.attributes.device_model_id:
                self.model = self.resource_models.setdefault(self.attributes.device_model_id, {}).get("model")


@dataclass
class AdcSubtypedResource(
    Generic[AdcResourceSubtypesT, AdcResourceAttributesT],
    AdcDeviceResource[AdcResourceAttributesT],
):
    """Base class for an Alarm.com device that uses subtypes."""

    resource_subtypes: type[AdcResourceSubtypesT] | None = field(default=None)
    subtype: AdcResourceSubtypesT | None = field(init=False)

    def __post_init__(self) -> None:
        """Initialize the resource."""

        super().__post_init__()

        # Subclasses declare `resource_subtypes = SensorSubtype` as a plain class attribute, but the dataclass
        # __init__ still assigns this field's default (None) on the instance, which hides it. Fall back to the
        # class attribute, or every subtype comes out None and checks such as "is this a motion sensor" never match.
        subtypes = self.resource_subtypes or type(self).resource_subtypes

        self.subtype = subtypes(getattr(self.attributes, "device_type", None)) if subtypes else None


DeviceState = TypeVar("DeviceState", bound=Enum)


class BaseStatefulDeviceState(Enum):
    """Base device states."""

    LOADING_STATE = -1


class BatteryLevel(Enum):
    """Battery level."""

    CRITICAL = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 4
    NONE = None


@dataclass(kw_only=True)
class BaseStatefulDeviceAttributes(Generic[DeviceState], AdcResourceAttributes):
    """Base attributes for an alarm.com device."""

    battery_level_pct: int | None = field(
        metadata=field_options(alias="battery_level_null")
        # The current battery level of the device as a percentage with null as the default value.
    )
    battery_level_classification: BatteryLevel = field(metadata={"description": "Indicate battery level status."})
    can_be_saved: bool = field(
        metadata={"description": "Whether the logged in context has write permissions for this device."}
    )
    can_confirm_state_change: bool = field(metadata={"description": "Whether the device can confirm its state change."})
    can_receive_commands: bool = field(metadata={"description": "Whether device supports receiving commands."})

    desired_state: DeviceState | None = field(metadata={"description": "Desired device state."}, default=None)
    has_permission_to_change_state: bool = field(
        metadata={"description": "Whether logged in user can change device state."}
    )
    remote_commands_enabled: bool = field(
        metadata={"description": "Whether device can be changed remotely via app or web."}
    )
    state: DeviceState = field(metadata={"description": "Current device state."})

    @property
    def can_change_state(self) -> bool:
        """Whether the logged in user can change this device's state."""

        return self.has_permission_to_change_state and self.remote_commands_enabled

    @property
    def interactive(self) -> bool:
        """Whether the device is ready to be interacted with."""

        return self.can_change_state and self.state != BaseStatefulDeviceState.LOADING_STATE

    @property
    def refreshing_state(self) -> bool:
        """Whether the device is in the refreshing state."""

        return self.loading or (self.state != self.desired_state)

    @property
    def loading(self) -> bool:
        """
        Whether the device is loading.

        None means undetermined.
        """

        return self.state == BaseStatefulDeviceState.LOADING_STATE


#
# BASE MANAGED DEVICE
#


@dataclass(kw_only=True)
class BaseManagedDeviceAttributes(
    BaseStatefulDeviceAttributes[DeviceState],
    Generic[DeviceState],
):
    """Base attributes for an alarm.com managed device."""

    has_state: bool = field(metadata={"description": "Does this device have a state?"}, default=False)
    is_malfunctioning: bool = field(
        metadata={"description": "Is the device currently set to a malfunction state."}, default=False
    )
    mac_address: str | None = field(
        metadata={"description": "The mac address for the device, if available."}, default=None
    )
    manufacturer: str | None = field(metadata={"description": "The manufacturer of the device."}, default=None)
    device_model: str | None = field(metadata={"description": "The device model."}, default=None)
    device_model_id: int | None = field(metadata={"description": "The device model id."}, default=None)

    # associatedCameraDeviceIds: dict  # { device_id: device_name } for all associated cameras.
    # canAccessWebSettings: bool  # Can the web settings be accessed?
    # isOAuth: bool  # Is the device an OAuth device?
    # isZWave: bool  # Is the device a ZWave device.
    # managedDeviceType: int  # The type of device.
    # webSettings: int # The route where the user can edit the device settings on the web.
