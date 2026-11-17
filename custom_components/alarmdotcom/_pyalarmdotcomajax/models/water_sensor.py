"""Alarm.com model for water sensors."""

from dataclasses import dataclass

from _pyalarmdotcomajax.models.base import (
    AdcDeviceResource,
    ResourceType,
)
from _pyalarmdotcomajax.models.sensor import SensorAttributes


@dataclass
class WaterSensor(AdcDeviceResource[SensorAttributes]):
    """Water sensor resource."""

    # Can be active / idle / wet / dry

    resource_type = ResourceType.WATER_SENSOR
    attributes_type = SensorAttributes
