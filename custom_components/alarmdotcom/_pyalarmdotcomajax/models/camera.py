"""Alarm.com model for cameras."""

from dataclasses import dataclass, field

from _pyalarmdotcomajax.models.base import (
    AdcDeviceResource,
    AdcResourceAttributes,
    BatteryLevel,
    ResourceType,
)


@dataclass
class CameraAttributes(AdcResourceAttributes):
    """Attributes of camera."""

    # fmt: off
    battery_level_null: int | None = field(metadata={"description": "The current battery level of the device, with null as the default value."})
    battery_level_classification: BatteryLevel  = field(metadata={"description": "Indicate battery level status."})
    low_battery: bool = field(metadata={"description": "Indicates whether the device has a low battery status."})
    is_malfunctioning: bool = field(metadata={"description": "Indicates whether the camera is currently in a malfunction state."})

    is_unreachable: bool = field(metadata={"description": "Indicates whether the camera is unreachable."})
    firmware_version: str | None = field(metadata={"description": "The firmware version of the device."})
    public_ip: str | None = field(metadata={"description": "The public IP address of the device."})
    private_ip: str | None = field(metadata={"description": "The private IP address of the device."})
    # fmt: on


@dataclass
class Camera(AdcDeviceResource[CameraAttributes]):
    """Image sensor image resource."""

    resource_type = ResourceType.CAMERA
    attributes_type = CameraAttributes
