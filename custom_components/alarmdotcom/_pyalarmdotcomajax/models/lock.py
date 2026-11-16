"""Alarm.com model for locks."""

from dataclasses import dataclass, field
from enum import Enum

from _pyalarmdotcomajax.models.base import (
    AdcDeviceResource,
    BaseManagedDeviceAttributes,
    ResourceType,
)


class LockState(Enum):
    """Lock states."""

    UNKNOWN = 0
    LOCKED = 1
    UNLOCKED = 2
    HIDDEN = 3


@dataclass
class LockAttributes(BaseManagedDeviceAttributes[LockState]):
    """Attributes of lock."""

    # fmt: off
    supports_latch_control: bool = field(metadata={"description": "Indicates if the lock supports remote latch control."}, default=False)

    # available_temporary_access_codes: int | None = field(metadata={"description": "The count of Temporary Access
    # Codes that have been pushed to the locks on the unit."})
    # can_enable_remote_commands: bool = field(metadata={"description": "The ability to enable or disable remote
    # commands. (Only for control point locks)"})
    # max_user_code_length: int = field(metadata={"description": "The maximum length of user codes supported by
    # this lock."})
    # supports_scheduled_user_codes: bool = field(metadata={"description": "Indicates if the lock supports
    # programming scheduled user codes."})
    # supports_temporary_user_codes: bool = field(metadata={"description": "Indicates if the lock supports
    # programming temporary user codes."})
    # total_temporary_access_codes: int | None = field(metadata={"description": "The total count of Temporary
    # Access Codes that have been pushed to the locks."})
    # fmt: on


@dataclass
class Lock(AdcDeviceResource[LockAttributes]):
    """Lock resource."""

    resource_type = ResourceType.LOCK
    attributes_type = LockAttributes
