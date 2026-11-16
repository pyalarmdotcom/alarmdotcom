"""
WebSocket state updates for sensors.

Regression cover for the case where a contact sensor stops updating in Home
Assistant while Alarm.com keeps reporting it: an Opened/Closed event that
arrives without an ``event_value``. Contact-sensor state lives entirely in
``subtype``, so such an event is perfectly valid and must still be applied.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from _pyalarmdotcomajax.const import ATTR_STATE
from _pyalarmdotcomajax.controllers.sensors import (
    SENSOR_EVENT_STATE_MAP,
    SUPPORTED_RESOURCE_EVENTS,
    SensorController,
)
from _pyalarmdotcomajax.controllers.water_sensors import WaterSensorController
from _pyalarmdotcomajax.models.sensor import Sensor, SensorState, SensorSubtype
from _pyalarmdotcomajax.websocket.messages import (
    EventWSMessage,
    PropertyChangeWSMessage,
    ResourceEventType,
    ResourcePropertyChangeType,
)

# Importing the component runs its sys.path shim, which puts the vendored
# library on sys.path as top-level `_pyalarmdotcomajax` — the same name the
# vendored modules import each other by. Importing it through the
# `custom_components.alarmdotcom.` prefix instead would load a second copy,
# with its own distinct enum classes that compare unequal to the real ones.
import custom_components.alarmdotcom  # noqa: F401
from custom_components.alarmdotcom.activity_history import (
    ACTIVITY_FEED_EVENT_TYPES,
    CONTACT_SENSOR_EVENT_TYPES,
    ActivityFeedTracker,
)


def _sensor(subtype: SensorSubtype) -> Sensor:
    """Build a Sensor stub carrying only what _handle_event touches."""
    resource = MagicMock(spec=Sensor)
    resource.id = "test-sensor-1"
    resource.subtype = subtype
    resource.api_resource = SimpleNamespace(attributes={})
    return resource


def _event(subtype: ResourceEventType, value: float | None) -> EventWSMessage:
    message = MagicMock(spec=EventWSMessage)
    message.subtype = subtype
    message.value = value
    return message


@pytest.mark.parametrize("value", [None, 0, 1])
@pytest.mark.asyncio
async def test_contact_sensor_opens_regardless_of_event_value(value) -> None:
    """
    `event_value` is meaningless for a contact sensor and must not gate state.

    This is the regression: gating on `message.value is not None` silently
    dropped every Opened/Closed event Alarm.com sent without one — no state
    change, no log line, no error.
    """
    controller = MagicMock(spec=SensorController)
    resource = _sensor(SensorSubtype.CONTACT_SENSOR)

    updated = await SensorController._handle_event(
        controller, resource, _event(ResourceEventType.Opened, value)
    )

    assert updated.api_resource.attributes[ATTR_STATE] == SensorState.OPEN.value


@pytest.mark.asyncio
async def test_motion_sensor_maps_to_active_not_open() -> None:
    """Motion sensors need IDLE/ACTIVE, which the class-level map cannot express."""
    controller = MagicMock(spec=SensorController)
    resource = _sensor(SensorSubtype.MOTION_SENSOR)

    updated = await SensorController._handle_event(
        controller, resource, _event(ResourceEventType.Opened, None)
    )

    assert updated.api_resource.attributes[ATTR_STATE] == SensorState.ACTIVE.value


def test_sensor_controller_declares_a_state_map() -> None:
    """Without it the unguarded path in _base_handle_event never runs for sensors."""
    assert SensorController._event_state_map is not None
    assert SensorController._event_state_map[ResourceEventType.Opened] == SensorState.OPEN
    assert SensorController._event_state_map[ResourceEventType.Closed] == SensorState.CLOSED


def test_subscription_is_derived_from_the_state_map() -> None:
    """Every mapped event must also be subscribed, or the map can never fire."""
    subscribed = set(SUPPORTED_RESOURCE_EVENTS.events or [])
    assert set(SENSOR_EVENT_STATE_MAP).issubset(subscribed)


def test_water_sensor_can_write_state() -> None:
    """It subscribed to Opened/Closed but had no way to act on them."""
    assert WaterSensorController._event_state_map is not None
    assert WaterSensorController._event_state_map[ResourceEventType.Opened] == SensorState.OPEN


def test_unknown_property_change_subtype_does_not_raise() -> None:
    """An unmapped subtype used to raise ValueError and drop the whole message."""
    assert ResourcePropertyChangeType(7) is ResourcePropertyChangeType.UNKNOWN
    assert ResourcePropertyChangeType(ResourcePropertyChangeType.LightColor.value) is (
        ResourcePropertyChangeType.LightColor
    )


def test_property_change_message_survives_an_unknown_subtype() -> None:
    """The end-to-end shape of #94: mashumaro must not fail the conversion."""
    message = PropertyChangeWSMessage.from_dict(
        {"unit_id": "1234", "device_id": 5, "property": 7, "property_value": 1}
    )
    assert message.subtype is ResourcePropertyChangeType.UNKNOWN
    assert message.full_device_id == "1234-5"


def _history_event() -> MagicMock:
    """Build a poll result standing in for one activity-history entry."""
    event = MagicMock()
    event.attributes.description = "Front Door Opened"
    event.attributes.event_type_name = "Opened"
    event.attributes.device_description = "Front Door"
    event.attributes.event_date = "2026-08-25T10:00:00Z"
    event.attributes.global_device_id = "id-1234-5"
    return event


def _tracker() -> MagicMock:
    tracker = MagicMock(spec=ActivityFeedTracker)
    tracker._recent_activity = []
    tracker.hub = MagicMock()
    return tracker


def test_contact_sensor_events_reach_the_bus_but_not_the_display() -> None:
    """
    The poll is an independent path; automations need it, the display does not.

    Contact-sensor open/close was excluded from the curated feed as display
    noise. That also denied automations the only source of those events that
    survives when the WebSocket route drops the state update (#94), so the bus
    event now fires while the Recent Activity list stays as it was.
    """
    tracker = _tracker()

    ActivityFeedTracker._fire_activity_event(tracker, _history_event(), feed=False)

    assert tracker._recent_activity == []
    tracker.hub.hass.bus.async_fire.assert_called_once()
    _name, payload = tracker.hub.hass.bus.async_fire.call_args[0]
    assert payload["device_id"] == "id-1234-5"
    assert payload["event_type_name"] == "Opened"


def test_curated_events_still_reach_the_display() -> None:
    """Widening the bus must not change what Recent Activity shows."""
    tracker = _tracker()
    event = _history_event()
    event.attributes.event_type_name = "Disarmed"

    ActivityFeedTracker._fire_activity_event(tracker, event)

    assert len(tracker._recent_activity) == 1
    tracker.hub.hass.bus.async_fire.assert_called_once()


def test_contact_sensors_stay_out_of_the_curated_set() -> None:
    """The original intent — they are display noise — is preserved."""
    assert not CONTACT_SENSOR_EVENT_TYPES & ACTIVITY_FEED_EVENT_TYPES
