"""Alarm.com model for systems."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import ClassVar

from _pyalarmdotcomajax.models.base import (
    AdcDeviceResource,
    AdcResourceAttributes,
    ResourceType,
)


class AccessControlSystemMode(IntEnum):
    """Enum of access control system modes."""

    DEFAULT = 0
    LOCKDOWN = 1
    RESTRICTED_ACCESS = 2


@dataclass
class SystemAttributes(AdcResourceAttributes):
    """Attributes of alarm system."""

    has_snap_shot_cameras: bool = field(default=False)
    supports_secure_arming: bool = field(default=False)
    remaining_image_quota: int = field(default=0)
    system_group_name: str = field(default="")
    unit_id: str = field(default="0")
    access_control_current_system_mode: AccessControlSystemMode = field(default=AccessControlSystemMode.DEFAULT)
    is_in_partial_lockdown: bool = field(default=False)
    icon: str = field(default="")


@dataclass
class System(AdcDeviceResource[SystemAttributes]):
    """System resource."""

    resource_type = ResourceType.SYSTEM
    attributes_type = SystemAttributes
    has_related_system: ClassVar[bool] = False
