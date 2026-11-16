"""
Tests for AdcActiveAutoOffTimersSensor and AutoOffManager's listener mechanism.

Uses the real `hass` fixture combined with a real AutoOffManager, since this
sensor's entire purpose is reacting live to that manager's own state changes
(not an Alarm.com resource event) - a mocked manager could too easily drift
from how add_listener/_notify_listeners actually behave.
"""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from custom_components.alarmdotcom.auto_off import AutoOffManager
from custom_components.alarmdotcom.const import DOMAIN
from custom_components.alarmdotcom.sensor import AdcActiveAutoOffTimersSensor

ENTITY_ID = "light.front_porch"
ENTITY_ID_2 = "light.back_porch"


@pytest.fixture
def manager(hass) -> AutoOffManager:
    """Build a fresh AutoOffManager for a test config entry."""
    return AutoOffManager(hass, "test-entry-id")


def _make_hub(hass) -> MagicMock:
    """Build a mock hub whose .hass is the real hass fixture, for real friendly-name lookups."""
    hub = MagicMock()
    hub.hass = hass
    hub.config_entry.entry_id = "test-entry-id"
    hub.api.active_system.id = "system-1"
    return hub


async def test_listener_fires_on_set(hass, manager: AutoOffManager) -> None:
    """A registered listener is called when a timer is set."""
    calls = 0

    def _on_change() -> None:
        nonlocal calls
        calls += 1

    manager.add_listener(_on_change)
    await manager.async_set(ENTITY_ID, timedelta(minutes=30))

    assert calls == 1
    await manager.async_cancel(ENTITY_ID)


async def test_listener_fires_on_cancel(hass, manager: AutoOffManager) -> None:
    """A registered listener is called when an active timer is cancelled."""
    await manager.async_set(ENTITY_ID, timedelta(minutes=30))
    calls = 0

    def _on_change() -> None:
        nonlocal calls
        calls += 1

    manager.add_listener(_on_change)
    await manager.async_cancel(ENTITY_ID)

    assert calls == 1


async def test_listener_does_not_fire_cancelling_nothing(hass, manager: AutoOffManager) -> None:
    """Cancelling an entity with no active timer does not spuriously notify listeners."""
    calls = 0

    def _on_change() -> None:
        nonlocal calls
        calls += 1

    manager.add_listener(_on_change)
    await manager.async_cancel(ENTITY_ID)

    assert calls == 0


async def test_unsubscribe_stops_future_notifications(hass, manager: AutoOffManager) -> None:
    """The unsubscribe function returned by add_listener actually stops future notifications."""
    calls = 0

    def _on_change() -> None:
        nonlocal calls
        calls += 1

    unsubscribe = manager.add_listener(_on_change)
    unsubscribe()
    await manager.async_set(ENTITY_ID, timedelta(minutes=30))

    assert calls == 0
    await manager.async_cancel(ENTITY_ID)


async def test_sensor_reflects_zero_with_no_active_timers(hass, manager: AutoOffManager) -> None:
    """With no active timers, the sensor reports a count of zero, not an error."""
    hub = _make_hub(hass)
    sensor = AdcActiveAutoOffTimersSensor(hub=hub, auto_off_manager=manager)

    assert sensor.native_value == 0
    assert sensor.extra_state_attributes == {"timers": {}}


async def test_sensor_counts_active_timers(hass, manager: AutoOffManager) -> None:
    """The sensor's state reflects the actual number of active timers present at construction time."""
    await manager.async_set(ENTITY_ID, timedelta(minutes=30))
    await manager.async_set(ENTITY_ID_2, timedelta(minutes=10))

    hub = _make_hub(hass)
    sensor = AdcActiveAutoOffTimersSensor(hub=hub, auto_off_manager=manager)

    assert sensor.native_value == 2

    await manager.async_cancel(ENTITY_ID)
    await manager.async_cancel(ENTITY_ID_2)


async def test_sensor_attribute_uses_friendly_name_when_available(hass, manager: AutoOffManager) -> None:
    """The timers attribute is keyed by the light's real friendly name, not its raw entity_id."""
    hass.states.async_set(ENTITY_ID, "on", {"friendly_name": "Front Porch"})
    off_at = await manager.async_set(ENTITY_ID, timedelta(minutes=30))

    hub = _make_hub(hass)
    sensor = AdcActiveAutoOffTimersSensor(hub=hub, auto_off_manager=manager)

    assert sensor.extra_state_attributes["timers"] == {"Front Porch": off_at.isoformat()}

    await manager.async_cancel(ENTITY_ID)


async def test_sensor_falls_back_to_entity_id_when_no_state_exists(hass, manager: AutoOffManager) -> None:
    """If a light has no known state (unlikely, but shouldn't crash), fall back to its raw entity_id."""
    off_at = await manager.async_set(ENTITY_ID, timedelta(minutes=30))

    hub = _make_hub(hass)
    sensor = AdcActiveAutoOffTimersSensor(hub=hub, auto_off_manager=manager)

    assert sensor.extra_state_attributes["timers"] == {ENTITY_ID: off_at.isoformat()}

    await manager.async_cancel(ENTITY_ID)


async def test_sensor_live_updates_via_on_change(hass, manager: AutoOffManager) -> None:
    """
    The sensor actually recomputes and writes new state when notified, not just at construction.

    This is the whole point of wiring into add_listener rather than just
    reading the manager once - simulates what async_added_to_hass's
    subscription achieves in the real entity lifecycle. Manually attaches
    hass/entity_id first, matching what actually adding the entity to hass
    would otherwise do, since async_write_ha_state requires it.
    """
    hub = _make_hub(hass)
    sensor = AdcActiveAutoOffTimersSensor(hub=hub, auto_off_manager=manager)
    sensor.hass = hass
    sensor.entity_id = "sensor.active_auto_off_timers"
    assert sensor.native_value == 0

    manager.add_listener(sensor._on_change)
    await manager.async_set(ENTITY_ID, timedelta(minutes=30))

    assert sensor.native_value == 1

    await manager.async_cancel(ENTITY_ID)
    assert sensor.native_value == 0


async def test_sensor_attaches_to_the_system_device(hass, manager: AutoOffManager) -> None:
    """The sensor attaches to the account's System device, matching the battery summary sensors."""
    hub = _make_hub(hass)
    sensor = AdcActiveAutoOffTimersSensor(hub=hub, auto_off_manager=manager)

    assert sensor.device_info == {"identifiers": {(DOMAIN, "system-1")}}
