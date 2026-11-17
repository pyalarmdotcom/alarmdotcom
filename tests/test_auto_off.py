"""
Tests for AutoOffManager (auto_off.py).

Uses the real `hass` fixture (a genuine, running Home Assistant test
instance) rather than mocking Store/scheduling directly - persistence and
restart behavior are the entire point of this feature, so they need to be
tested against the real mechanisms, not a mock that could silently diverge
from how Store/async_track_point_in_time actually behave.
"""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.alarmdotcom.auto_off import AutoOffManager

ENTITY_ID = "light.front_porch"


@pytest.fixture
def manager(hass):
    """Build a fresh AutoOffManager for a test config entry."""
    return AutoOffManager(hass, "test-entry-id")


@pytest.fixture
def mock_light_turn_off(hass):
    """Register a real (mocked) light.turn_off service handler and return the mock to assert against."""
    mock_handler = AsyncMock()
    hass.services.async_register("light", "turn_off", mock_handler)
    return mock_handler


async def test_set_schedules_and_returns_off_at(hass, manager: AutoOffManager) -> None:
    """Setting a timer returns the correct off-at time and makes it queryable."""
    before = dt_util.utcnow()
    off_at = await manager.async_set(ENTITY_ID, timedelta(minutes=30))

    assert off_at >= before + timedelta(minutes=30)
    assert manager.get_off_at(ENTITY_ID) == off_at

    await manager.async_cancel(ENTITY_ID)


async def test_set_persists_to_storage(hass, manager: AutoOffManager) -> None:
    """A scheduled timer is actually written to persistent storage, not just kept in memory."""
    off_at = await manager.async_set(ENTITY_ID, timedelta(minutes=15))

    stored = await manager._store.async_load()
    assert stored is not None
    assert stored[ENTITY_ID] == off_at.isoformat()

    await manager.async_cancel(ENTITY_ID)


async def test_cancel_clears_timer_and_storage(hass, manager: AutoOffManager) -> None:
    """Cancelling removes the timer from memory and from persistent storage."""
    await manager.async_set(ENTITY_ID, timedelta(minutes=30))

    had_one = await manager.async_cancel(ENTITY_ID)

    assert had_one is True
    assert manager.get_off_at(ENTITY_ID) is None
    stored = await manager._store.async_load()
    assert not stored


async def test_cancel_with_no_active_timer_returns_false(hass, manager: AutoOffManager) -> None:
    """Cancelling an entity with no pending timer is a safe no-op, not an error."""
    had_one = await manager.async_cancel(ENTITY_ID)

    assert had_one is False


async def test_set_replaces_an_existing_timer(hass, manager: AutoOffManager) -> None:
    """Setting a new timer for the same entity replaces the old one rather than stacking."""
    await manager.async_set(ENTITY_ID, timedelta(minutes=30))
    second_off_at = await manager.async_set(ENTITY_ID, timedelta(minutes=5))

    assert manager.get_off_at(ENTITY_ID) == second_off_at
    stored = await manager._store.async_load()
    assert stored[ENTITY_ID] == second_off_at.isoformat()

    await manager.async_cancel(ENTITY_ID)


async def test_notify_external_off_clears_pending_timer(hass, manager: AutoOffManager) -> None:
    """A light turned off some other way (manually, from the Alarm.com app) clears its own timer."""
    await manager.async_set(ENTITY_ID, timedelta(minutes=30))

    manager.notify_state_changed_externally(ENTITY_ID, is_on=False)
    await hass.async_block_till_done()

    assert manager.get_off_at(ENTITY_ID) is None


async def test_notify_external_on_does_not_clear_pending_timer(hass, manager: AutoOffManager) -> None:
    """A light turning back on (or already on) should not disturb a pending timer."""
    off_at = await manager.async_set(ENTITY_ID, timedelta(minutes=30))

    manager.notify_state_changed_externally(ENTITY_ID, is_on=True)
    await hass.async_block_till_done()

    assert manager.get_off_at(ENTITY_ID) == off_at

    await manager.async_cancel(ENTITY_ID)


async def test_load_with_future_time_reschedules_without_firing(
    hass, manager: AutoOffManager, mock_light_turn_off: AsyncMock
) -> None:
    """A timer whose off-at time is still in the future is rescheduled, not fired immediately on load."""
    future = dt_util.utcnow() + timedelta(minutes=10)
    await manager._store.async_save({ENTITY_ID: future.isoformat()})

    fresh_manager = AutoOffManager(hass, "test-entry-id")
    await fresh_manager.async_load()
    await hass.async_block_till_done()

    mock_light_turn_off.assert_not_called()
    assert fresh_manager.get_off_at(ENTITY_ID) == future

    await fresh_manager.async_cancel(ENTITY_ID)


async def test_load_with_past_time_fires_immediately(
    hass, manager: AutoOffManager, mock_light_turn_off: AsyncMock
) -> None:
    """
    A timer whose off-at time already passed while Home Assistant was offline fires immediately on load.

    This is the actual restart-survival behavior the whole feature exists
    for - a plain automation using Wait would simply have lost this
    scheduled action entirely.
    """
    past = dt_util.utcnow() - timedelta(minutes=5)
    await manager._store.async_save({ENTITY_ID: past.isoformat()})

    fresh_manager = AutoOffManager(hass, "test-entry-id")
    await fresh_manager.async_load()
    await hass.async_block_till_done()

    mock_light_turn_off.assert_called_once()
    call_args = mock_light_turn_off.call_args[0][0]
    assert call_args.data == {"entity_id": ENTITY_ID}
    assert fresh_manager.get_off_at(ENTITY_ID) is None
