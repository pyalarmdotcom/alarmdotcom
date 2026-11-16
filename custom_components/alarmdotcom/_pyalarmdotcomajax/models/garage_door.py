"""Alarm.com model for garage doors."""

from dataclasses import dataclass
from enum import Enum

from _pyalarmdotcomajax.models.base import (
    AdcDeviceResource,
    BaseManagedDeviceAttributes,
    ResourceType,
)


class GarageDoorState(Enum):
    """Enum of gate states."""

    # https://www.alarm.com/web/system/assets/customer-ember/enums/GarageDoorStatus.js

    UNKNOWN = 0
    OPEN = 1
    CLOSED = 2
    HIDDEN = 3


@dataclass
class GarageDoorAttributes(BaseManagedDeviceAttributes[GarageDoorState]):
    """Attributes of a garage door device."""


@dataclass
class GarageDoor(AdcDeviceResource[GarageDoorAttributes]):
    """Garage door resource."""

    resource_type = ResourceType.GARAGE_DOOR
    attributes_type = GarageDoorAttributes
