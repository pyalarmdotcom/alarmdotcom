"""Alarm.com model for WaterValves."""

from dataclasses import dataclass
from enum import Enum

from _pyalarmdotcomajax.models.base import (
    AdcDeviceResource,
    BaseManagedDeviceAttributes,
    ResourceType,
)


class WaterValveState(Enum):
    """Enum of water valve states."""

    UNKNOWN = 0
    OPEN = 1
    CLOSED = 2


@dataclass(kw_only=True)
class WaterValveAttributes(BaseManagedDeviceAttributes[WaterValveState]):
    """Attributes of a water valve."""


@dataclass
class WaterValve(AdcDeviceResource[WaterValveAttributes]):
    """WaterValve resource."""

    resource_type = ResourceType.WATER_VALVE
    attributes_type = WaterValveAttributes
