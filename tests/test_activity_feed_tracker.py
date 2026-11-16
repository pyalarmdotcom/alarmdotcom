"""
Tests for ActivityFeedTracker (activity_history.py).

Mocks hub.api.get_activity_history and hub.api.locks directly - the
fetch mechanism itself is already covered by test_get_activity_history.py;
these tests focus on what's new here: filtering, deduplication, and the
change-notification mechanism.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.alarmdotcom.activity_history import (
    RECENT_ACTIVITY_MAX_LEN,
    ActivityFeedTracker,
)

FRONT_DOOR_ID = "110353471-1201"
PATIO_DOOR_ID = "110353471-1200"
GARAGE_DOOR_ID = "110353471-2205"


def _make_lock(resource_id: str) -> MagicMock:
    """Build a mock lock resource with just the .id attribute needed."""
    lock = MagicMock()
    lock.id = resource_id
    return lock


def _make_event(
    event_type_name: str,
    global_device_id: str,
    event_date: str,
    unlocked_by_name: str | None,
    *,
    description: str = "Test event",
    device_description: str = "Test Device",
    unlock_method: str | None = "unspecified",
) -> MagicMock:
    """Build a mock HistoryEvent with just the attributes ActivityFeedTracker actually reads."""
    event = MagicMock()
    event.attributes.event_type_name = event_type_name
    event.attributes.global_device_id = global_device_id
    event.attributes.event_date = event_date
    event.attributes.unlocked_by_name = unlocked_by_name
    event.attributes.description = description
    event.attributes.device_description = device_description

    if unlock_method == "unspecified":
        # Caller didn't pass one explicitly - default to "keypad" when a
        # name is present (matching real data, where unlocked_by_name is
        # only ever non-None for keypad unlocks), otherwise None.
        event.attributes.unlock_method = "keypad" if unlocked_by_name else None
    else:
        event.attributes.unlock_method = unlock_method

    return event


def _make_hub(
    locks: list[MagicMock],
    events: list[MagicMock],
    *,
    options: dict | None = None,
    garage_doors: list[MagicMock] | None = None,
) -> MagicMock:
    """Build a mock hub whose api returns the given locks, garage doors, and get_activity_history events."""
    hub = MagicMock()
    hub.api.locks = locks
    hub.api.garage_doors = garage_doors or []
    hub.api.get_activity_history = AsyncMock(return_value=events)
    hub.config_entry.options = options or {}
    return hub


@pytest.fixture
def tracker(hass) -> ActivityFeedTracker:
    """Build a fresh, unstarted ActivityFeedTracker (no locks, no events by default)."""
    hub = _make_hub(locks=[_make_lock(FRONT_DOOR_ID)], events=[])
    hub.hass = hass
    return ActivityFeedTracker(hub)


async def test_keypad_unlock_is_tracked() -> None:
    """A DoorUnlocked event for a known lock, with attribution, gets tracked."""
    event = _make_event("DoorUnlocked", FRONT_DOOR_ID, "2026-07-14T02:22:56.307Z", "Chris Pulliam")
    hub = _make_hub(locks=[_make_lock(FRONT_DOOR_ID)], events=[event])
    tracker = ActivityFeedTracker(hub)

    await tracker.async_poll()

    result = tracker.get_last_unlock(FRONT_DOOR_ID)
    assert result is not None
    assert result["unlocked_by"] == "Chris Pulliam"
    assert result["unlock_method"] == "keypad"
    assert result["unlocked_at"] == datetime(2026, 7, 14, 2, 22, 56, 307000, tzinfo=UTC)


async def test_unattributed_unlock_is_still_tracked_with_none() -> None:
    """A DoorUnlocked event with no attribution (web session, manual) is still tracked - as None, not skipped."""
    event = _make_event("DoorUnlocked", FRONT_DOOR_ID, "2026-07-14T02:22:56.307Z", None)
    hub = _make_hub(locks=[_make_lock(FRONT_DOOR_ID)], events=[event])
    tracker = ActivityFeedTracker(hub)

    await tracker.async_poll()

    result = tracker.get_last_unlock(FRONT_DOOR_ID)
    assert result is not None
    assert result["unlocked_by"] is None


async def test_non_unlock_events_are_ignored(tracker: ActivityFeedTracker) -> None:
    """Events that aren't DoorUnlocked (light on/off, arm/disarm, etc.) don't get tracked at all."""
    event = _make_event("LightTurnedOn", FRONT_DOOR_ID, "2026-07-14T02:22:56.307Z", None)
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])

    await tracker.async_poll()

    assert tracker.get_last_unlock(FRONT_DOOR_ID) is None


async def test_unlock_for_unknown_device_is_ignored(tracker: ActivityFeedTracker) -> None:
    """A DoorUnlocked event for a device that isn't one of this account's known locks is ignored."""
    event = _make_event("DoorUnlocked", "some-other-device-id", "2026-07-14T02:22:56.307Z", "Someone")
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])

    await tracker.async_poll()

    assert tracker.get_last_unlock("some-other-device-id") is None


async def test_multiple_locks_are_tracked_independently() -> None:
    """Two different locks unlocking get tracked separately, not overwriting each other."""
    events = [
        _make_event("DoorUnlocked", FRONT_DOOR_ID, "2026-07-14T02:22:56.307Z", "Chris Pulliam"),
        _make_event("DoorUnlocked", PATIO_DOOR_ID, "2026-07-13T23:35:28.823Z", None),
    ]
    hub = _make_hub(locks=[_make_lock(FRONT_DOOR_ID), _make_lock(PATIO_DOOR_ID)], events=events)
    tracker = ActivityFeedTracker(hub)

    await tracker.async_poll()

    assert tracker.get_last_unlock(FRONT_DOOR_ID)["unlocked_by"] == "Chris Pulliam"
    assert tracker.get_last_unlock(PATIO_DOOR_ID)["unlocked_by"] is None


async def test_older_event_does_not_overwrite_a_newer_tracked_record() -> None:
    """A same-or-older event (e.g. from overlapping poll windows) never overwrites a newer tracked record."""
    hub = _make_hub(locks=[_make_lock(FRONT_DOOR_ID)], events=[])
    tracker = ActivityFeedTracker(hub)

    newer_event = _make_event("DoorUnlocked", FRONT_DOOR_ID, "2026-07-14T02:22:56.307Z", "Chris Pulliam")
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[newer_event])
    await tracker.async_poll()

    older_event = _make_event("DoorUnlocked", FRONT_DOOR_ID, "2026-07-13T23:35:28.823Z", "Someone Else")
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[older_event])
    await tracker.async_poll()

    assert tracker.get_last_unlock(FRONT_DOOR_ID)["unlocked_by"] == "Chris Pulliam"


async def test_listener_notified_when_new_attribution_found(tracker: ActivityFeedTracker) -> None:
    """A registered listener fires when a poll actually finds something new."""
    calls = 0

    def _on_change() -> None:
        nonlocal calls
        calls += 1

    tracker.add_listener(_on_change)
    event = _make_event("DoorUnlocked", FRONT_DOOR_ID, "2026-07-14T02:22:56.307Z", "Chris Pulliam")
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])

    await tracker.async_poll()

    assert calls == 1


async def test_listener_not_notified_when_nothing_new(tracker: ActivityFeedTracker) -> None:
    """A poll that finds nothing new (empty response) does not spuriously notify listeners."""
    calls = 0

    def _on_change() -> None:
        nonlocal calls
        calls += 1

    tracker.add_listener(_on_change)

    await tracker.async_poll()

    assert calls == 0


async def test_unsubscribe_stops_future_notifications(tracker: ActivityFeedTracker) -> None:
    """The unsubscribe function returned by add_listener actually stops future notifications."""
    calls = 0

    def _on_change() -> None:
        nonlocal calls
        calls += 1

    unsubscribe = tracker.add_listener(_on_change)
    unsubscribe()

    event = _make_event("DoorUnlocked", FRONT_DOOR_ID, "2026-07-14T02:22:56.307Z", "Chris Pulliam")
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])
    await tracker.async_poll()

    assert calls == 0


async def test_a_failed_poll_does_not_raise(tracker: ActivityFeedTracker) -> None:
    """A poll that fails (e.g. network error, unexpected response shape) is logged and swallowed, not raised."""
    tracker.hub.api.get_activity_history = AsyncMock(side_effect=ConnectionError("boom"))

    # Must not raise - this is the actual behavior under test.
    await tracker.async_poll()

    assert tracker.get_last_unlock(FRONT_DOOR_ID) is None


async def test_get_last_unlock_returns_none_for_untracked_lock(tracker: ActivityFeedTracker) -> None:
    """A lock with no tracked unlock at all returns None, not an error."""
    assert tracker.get_last_unlock(FRONT_DOOR_ID) is None


async def test_new_attribution_logs_at_info_level(tracker: ActivityFeedTracker, caplog: pytest.LogCaptureFixture) -> None:
    """
    A real new unlock logs at INFO level, confirmable without debug logging or a live test.

    This is deliberately the one thing this poller logs at INFO rather
    than debug - it only fires on an actual new unlock, not every
    15-second poll, so it's a useful confirmation signal rather than log
    noise.
    """
    event = _make_event("DoorUnlocked", FRONT_DOOR_ID, "2026-07-14T02:22:56.307Z", "Chris Pulliam")
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])

    with caplog.at_level("INFO"):
        await tracker.async_poll()

    assert "Chris Pulliam" in caplog.text
    assert FRONT_DOOR_ID in caplog.text


async def test_no_new_attribution_does_not_log_at_info_level(tracker: ActivityFeedTracker, caplog: pytest.LogCaptureFixture) -> None:
    """An empty poll (nothing new) produces no INFO-level noise."""
    with caplog.at_level("INFO"):
        await tracker.async_poll()

    assert caplog.text == ""


# --- Curated activity feed ---


async def test_curated_event_fires_on_the_event_bus(hass, tracker: ActivityFeedTracker) -> None:
    """A curated event type (e.g. ArmedStay) fires on Home Assistant's event bus with the right data."""
    event = _make_event(
        "ArmedStay", "110353471-127", "2026-07-14T03:24:37.867Z", None,
        description="Armed Stay by Web", device_description="System",
    )
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])

    captured = []
    hass.bus.async_listen("alarmdotcom_activity", captured.append)

    await tracker.async_poll()
    await hass.async_block_till_done()

    assert len(captured) == 1
    assert captured[0].data["description"] == "Armed Stay by Web"
    assert captured[0].data["event_type_name"] == "ArmedStay"
    assert captured[0].data["device_description"] == "System"


async def test_non_curated_event_does_not_fire_on_the_event_bus(hass, tracker: ActivityFeedTracker) -> None:
    """A non-curated event type (e.g. LightTurnedOn, deliberately excluded - see module docstring) does not fire."""
    event = _make_event("LightTurnedOn", "110353471-1220", "2026-07-14T03:24:37.867Z", None)
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])

    captured = []
    hass.bus.async_listen("alarmdotcom_activity", captured.append)

    await tracker.async_poll()
    await hass.async_block_till_done()

    assert captured == []


async def test_curated_event_appears_in_recent_activity(tracker: ActivityFeedTracker) -> None:
    """A curated event is added to the recent-activity rolling list, retrievable via get_recent_activity."""
    event = _make_event(
        "DoorLocked", FRONT_DOOR_ID, "2026-07-14T03:24:37.773Z", None,
        description="Locked from Keypad", device_description="Front Door",
    )
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])

    await tracker.async_poll()

    recent = tracker.get_recent_activity()
    assert len(recent) == 1
    assert recent[0]["description"] == "Locked from Keypad"
    assert recent[0]["event_type_name"] == "DoorLocked"
    assert recent[0]["device_description"] == "Front Door"


async def test_recent_activity_is_newest_first(tracker: ActivityFeedTracker) -> None:
    """get_recent_activity returns the most recently polled curated event first."""
    first_event = _make_event("DoorLocked", FRONT_DOOR_ID, "t1", None, description="First")
    second_event = _make_event("DoorLocked", FRONT_DOOR_ID, "t2", None, description="Second")
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[first_event, second_event])

    await tracker.async_poll()

    recent = tracker.get_recent_activity()
    assert [entry["description"] for entry in recent] == ["Second", "First"]


async def test_recent_activity_is_bounded(tracker: ActivityFeedTracker) -> None:
    """The recent-activity list never grows past its configured max length."""
    events = [
        _make_event("DoorLocked", FRONT_DOOR_ID, f"t{i}", None, description=f"Event {i}")
        for i in range(RECENT_ACTIVITY_MAX_LEN + 5)
    ]
    tracker.hub.api.get_activity_history = AsyncMock(return_value=events)

    await tracker.async_poll()

    assert len(tracker.get_recent_activity()) == RECENT_ACTIVITY_MAX_LEN


async def test_curated_feed_notifies_listeners_even_without_a_lock_change(tracker: ActivityFeedTracker) -> None:
    """A curated non-lock event (e.g. ArmedStay) still notifies listeners, not just lock unlock changes."""
    calls = 0

    def _on_change() -> None:
        nonlocal calls
        calls += 1

    tracker.add_listener(_on_change)
    event = _make_event("ArmedStay", "110353471-127", "2026-07-14T03:24:37.867Z", None)
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])

    await tracker.async_poll()

    assert calls == 1


# --- Garage door disambiguation ---


async def test_known_garage_door_open_event_fires_on_the_event_bus(hass) -> None:
    """
    An Opened/Closed event for a known garage door resource is included in the curated feed.

    This is the actual disambiguation this feature needed: Opened/Closed
    is not in ACTIVITY_FEED_EVENT_TYPES at all (too ambiguous on its own -
    see module comments), but a garage door specifically is included via
    a separate cross-reference against hub.api.garage_doors, the same
    controller cover.py already uses.
    """
    garage_door = MagicMock()
    garage_door.id = GARAGE_DOOR_ID
    hub = _make_hub(locks=[], events=[], garage_doors=[garage_door])
    hub.hass = hass
    tracker = ActivityFeedTracker(hub)

    event = _make_event(
        "Closed", GARAGE_DOOR_ID, "2026-07-13T23:45:41Z", None,
        description="Closed", device_description="Garage Door",
    )
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])

    captured = []
    hass.bus.async_listen("alarmdotcom_activity", captured.append)

    await tracker.async_poll()
    await hass.async_block_till_done()

    assert len(captured) == 1
    assert captured[0].data["device_description"] == "Garage Door"


async def test_ordinary_sensor_open_event_is_not_included(hass) -> None:
    """
    An Opened/Closed event for an ordinary window/door sensor (not a known garage door) stays excluded.

    Same event_type_name as the garage door case above - the only
    difference is global_device_id not matching any known garage door
    resource, which is exactly the ambiguity this feature exists to
    resolve.
    """
    garage_door = MagicMock()
    garage_door.id = GARAGE_DOOR_ID
    hub = _make_hub(locks=[], events=[], garage_doors=[garage_door])
    hub.hass = hass
    tracker = ActivityFeedTracker(hub)

    event = _make_event(
        "OpenedClosed", "110353471-2", "2026-07-14T03:24:34.543Z", None,
        description="Opened/Closed", device_description="Front",
    )
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])

    captured = []
    hass.bus.async_listen("alarmdotcom_activity", captured.append)

    await tracker.async_poll()
    await hass.async_block_till_done()

    assert captured == []


async def test_garage_door_event_appears_in_recent_activity(hass) -> None:
    """A known garage door event also lands in the recent-activity rolling list, same as any other curated event."""
    garage_door = MagicMock()
    garage_door.id = GARAGE_DOOR_ID
    hub = _make_hub(locks=[], events=[], garage_doors=[garage_door])
    hub.hass = hass
    tracker = ActivityFeedTracker(hub)

    event = _make_event(
        "Opened", GARAGE_DOOR_ID, "2026-07-13T23:37:18Z", None,
        description="Opened", device_description="Garage Door",
    )
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])

    await tracker.async_poll()

    recent = tracker.get_recent_activity()
    assert len(recent) == 1
    assert recent[0]["device_description"] == "Garage Door"


async def test_no_garage_doors_on_the_account_means_nothing_matches(hass) -> None:
    """With zero garage doors configured (the default in most tests), no Opened/Closed event ever matches."""
    hub = _make_hub(locks=[], events=[])  # garage_doors defaults to []
    hub.hass = hass
    tracker = ActivityFeedTracker(hub)

    event = _make_event("Closed", GARAGE_DOOR_ID, "2026-07-13T23:45:41Z", None)
    tracker.hub.api.get_activity_history = AsyncMock(return_value=[event])

    captured = []
    hass.bus.async_listen("alarmdotcom_activity", captured.append)

    await tracker.async_poll()
    await hass.async_block_till_done()

    assert captured == []


# --- Configurable poll interval ---


async def test_async_start_uses_configured_interval(hass) -> None:
    """async_start schedules polling using the user-configured interval from config_entry.options, when set."""
    hub = _make_hub(locks=[], events=[], options={"activity_poll_interval": 45})
    hub.hass = hass
    tracker = ActivityFeedTracker(hub)

    with patch(
        "custom_components.alarmdotcom.activity_history.async_track_time_interval"
    ) as mock_track:
        tracker.async_start()

    mock_track.assert_called_once()
    scheduled_interval = mock_track.call_args.args[2]
    assert scheduled_interval == timedelta(seconds=45)


async def test_async_start_falls_back_to_default_interval(hass) -> None:
    """async_start uses the default interval when no option has been configured."""
    hub = _make_hub(locks=[], events=[], options={})
    hub.hass = hass
    tracker = ActivityFeedTracker(hub)

    with patch(
        "custom_components.alarmdotcom.activity_history.async_track_time_interval"
    ) as mock_track:
        tracker.async_start()

    scheduled_interval = mock_track.call_args.args[2]
    assert scheduled_interval == timedelta(seconds=15)
