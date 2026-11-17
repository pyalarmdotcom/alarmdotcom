"""Alarm.com controller for water sensors."""

from types import MappingProxyType

from _pyalarmdotcomajax.controllers.base import BaseController, device_controller
from _pyalarmdotcomajax.models.base import ResourceType
from _pyalarmdotcomajax.models.sensor import SensorState
from _pyalarmdotcomajax.models.water_sensor import WaterSensor
from _pyalarmdotcomajax.websocket.client import SupportedResourceEvents
from _pyalarmdotcomajax.websocket.messages import ResourceEventType

WATER_SENSOR_EVENT_STATE_MAP = MappingProxyType(
    {
        ResourceEventType.Opened: SensorState.OPEN,
        ResourceEventType.Closed: SensorState.CLOSED,
    }
)


@device_controller(ResourceType.WATER_SENSOR, WaterSensor)
class WaterSensorController(BaseController[WaterSensor]):
    """Controller for water sensors."""

    # This controller subscribed to Opened/Closed but defined neither a state
    # map nor a _handle_event override, so every water-leak event reached
    # _base_handle_event and was discarded with the resource unmodified.
    _event_state_map = WATER_SENSOR_EVENT_STATE_MAP
    _supported_resource_events = SupportedResourceEvents(events=[*WATER_SENSOR_EVENT_STATE_MAP.keys()])
