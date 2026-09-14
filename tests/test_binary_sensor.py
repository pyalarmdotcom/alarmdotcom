"""Tests for Alarm.com binary sensors."""

from unittest.mock import MagicMock

import pyalarmdotcomajax as pyadc
import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.alarmdotcom.binary_sensor import device_class_fn


@pytest.mark.parametrize(
    "sensor_subtype",
    [
        pyadc.sensor.SensorSubtype.GLASS_BREAK_DETECTOR,
        pyadc.sensor.SensorSubtype.PANEL_GLASS_BREAK_DETECTOR,
    ],
)
def test_glass_break_device_class(sensor_subtype: pyadc.sensor.SensorSubtype) -> None:
    """Test glass break sensors use the glass break device class."""
    resource = MagicMock(spec=pyadc.sensor.Sensor)
    resource.attributes.device_type = sensor_subtype

    hub = MagicMock()
    hub.api.sensors.get.return_value = resource
    hub.api.water_sensors.get.return_value = None

    assert (  # noqa: S101
        device_class_fn(hub, "sensor_id") is BinarySensorDeviceClass.GLASS_BREAK
    )
