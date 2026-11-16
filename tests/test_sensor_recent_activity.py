"""
Tests for AdcRecentActivitySensor.

Uses a real ActivityFeedTracker (not a mock) combined with the real hass
fixture, matching the same reasoning as test_sensor_active_auto_off_timers.py:
this sensor's entire purpose is reacting live to the tracker's own
listener mechanism, which a mocked tracker could too easily drift from.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.alarmdotcom.activity_history import ActivityFeedTracker
from custom_components.alarmdotcom.const import DOMAIN
from custom_components.alarmdotcom.sensor import AdcRecentActivitySensor


def _make_hub(hass) -> MagicMock:
    """Build a mock hub whose .hass is the real hass fixture."""
    hub = MagicMock()
    hub.hass = hass
    hub.config_entry.entry_id = "test-entry-id"
    hub.config_entry.options = {}
    hub.api.active_system.id = "system-1"
    hub.api.locks = []
    return hub


def _make_event(description: str, event_type_name: str, device_description: str, event_date: str) -> MagicMock:
    event = MagicMock()
    event.attributes.description = description
    event.attributes.event_type_name = event_type_name
    event.attributes.device_description = device_description
    event.attributes.event_date = event_date
    event.attributes.global_device_id = "110353471-1"
    event.attributes.unlocked_by_name = None
    return event


@pytest.fixture
def tracker(hass) -> ActivityFeedTracker:
    """Build a fresh ActivityFeedTracker for a mock hub."""
    return ActivityFeedTracker(_make_hub(hass))


async def test_sensor_shows_no_recent_activity_with_nothing_tracked(hass, tracker: ActivityFeedTracker) -> None:
    """With no curated activity yet, the sensor reports a clear placeholder, not an error or blank state."""
    sensor = AdcRecentActivitySensor(hub=tracker.hub, activity_feed_tracker=tracker)

    assert sensor.native_value == "No recent activity"
    assert sensor.extra_state_attributes == {"recent_events": []}


async def test_sensor_reflects_the_most_recent_curated_event(hass, tracker: ActivityFeedTracker) -> None:
    """The sensor's state is the description of the most recent curated event."""
    event = _make_event("Armed Stay by Web", "ArmedStay", "System", "2026-07-14T03:24:37.867Z")
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])
    await tracker.async_poll()

    sensor = AdcRecentActivitySensor(hub=tracker.hub, activity_feed_tracker=tracker)

    assert sensor.native_value == "Armed Stay by Web"
    assert len(sensor.extra_state_attributes["recent_events"]) == 1


async def test_sensor_live_updates_via_on_change(hass, tracker: ActivityFeedTracker) -> None:
    """The sensor recomputes and writes new state when the tracker finds new curated activity, not just at construction."""
    sensor = AdcRecentActivitySensor(hub=tracker.hub, activity_feed_tracker=tracker)
    sensor.hass = hass
    sensor.entity_id = "sensor.recent_activity"
    assert sensor.native_value == "No recent activity"

    tracker.add_listener(sensor._on_change)
    event = _make_event("Locked from Keypad", "DoorLocked", "Front Door", "2026-07-14T03:24:37.773Z")
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])
    await tracker.async_poll()

    assert sensor.native_value == "Locked from Keypad"


async def test_sensor_attaches_to_the_system_device(hass, tracker: ActivityFeedTracker) -> None:
    """The sensor attaches to the account's System device, matching the other summary sensors."""
    sensor = AdcRecentActivitySensor(hub=tracker.hub, activity_feed_tracker=tracker)

    assert sensor.device_info == {"identifiers": {(DOMAIN, "system-1")}}
