"""Malfunction subsensor."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
)

from .entity import AdcControllerT, AdcEntityDescription, AdcManagedDeviceT

if TYPE_CHECKING:
    from .hub import AlarmHub

log = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AdcSensorEntityDescription(
    Generic[AdcManagedDeviceT, AdcControllerT],
    AdcEntityDescription[AdcManagedDeviceT, AdcControllerT],
    SensorEntityDescription,
):
    """Base Alarm.com binary sensor entity description."""

    device_class_fn: Callable[[AlarmHub, str], SensorDeviceClass | None]
    """Return the device class for the binary sensor."""


# ATTRIBUTE_SENSORS: Final = [
#     AdcSensorEntityDescription(
#         key="battery",
#         name="Battery",
#         entity_category=EntityCategory.DIAGNOSTIC,
#         device_class=SensorDeviceClass.BATTERY,
#         has_entity_name=False,
#         value_fn=lambda device: device.battery_alert,
#         supported_fn=lambda device: device.battery_critical is not None
#         and device.battery_low is not None,
#     ),
# ]
