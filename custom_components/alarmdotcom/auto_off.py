"""
Auto-off timer management for Alarm.com lights.

Lets any light entity in this integration be scheduled to turn off after a
duration. Deliberately more than a plain Home Assistant automation using a
"wait then turn off" action, in two ways an automation can't match on its
own:

- Survives a Home Assistant restart: the scheduled off-time is persisted via
  Store, and reloaded on startup. A timer whose time already passed while
  Home Assistant was offline fires immediately (catch-up); one still in the
  future is rescheduled for its remaining duration.
- The scheduled off-time is exposed as a queryable entity attribute
  (`auto_off_at` on the light itself - see light.py), so "time remaining"
  is available to templates and other automations without needing a
  separate helper entity.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


class AutoOffManager:
    """Tracks and persists auto-off timers for light entities, keyed by entity_id."""

    def __init__(self, hass: HomeAssistant, config_entry_id: str) -> None:
        """Initialize the manager for one config entry."""

        self.hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, f"alarmdotcom_auto_off_{config_entry_id}")
        # entity_id -> scheduled off time (aware datetime, UTC)
        self._off_at: dict[str, datetime] = {}
        # entity_id -> unsubscribe callback for its scheduled turn-off
        self._unsub: dict[str, CALLBACK_TYPE] = {}
        # Callbacks to notify whenever a timer is set, cancelled, or fires -
        # e.g. the active-timers summary sensor in sensor.py, which needs to
        # recompute live rather than only reflecting state from startup.
        self._change_listeners: list[Callable[[], None]] = []

    async def async_load(self) -> None:
        """Load persisted timers on startup, firing any that are already due."""

        stored: dict[str, str] = await self._store.async_load() or {}
        now = dt_util.utcnow()

        for entity_id, off_at_iso in stored.items():
            off_at = dt_util.parse_datetime(off_at_iso)
            if off_at is None:
                continue
            if off_at <= now:
                _LOGGER.debug(
                    "Auto-off for %s was due while Home Assistant was offline - turning off now.",
                    entity_id,
                )
                self.hass.async_create_task(self._async_fire(entity_id))
            else:
                self._schedule(entity_id, off_at)

    async def async_set(self, entity_id: str, duration: timedelta) -> datetime:
        """Schedule entity_id to turn off after duration from now. Returns the off-at time."""

        off_at = dt_util.utcnow() + duration
        self._cancel_existing(entity_id)
        self._schedule(entity_id, off_at)
        await self._async_persist()
        self._notify_listeners()
        return off_at

    async def async_cancel(self, entity_id: str) -> bool:
        """Cancel a pending auto-off for entity_id. Returns True if one was actually active."""

        had_one = entity_id in self._off_at
        self._cancel_existing(entity_id)
        await self._async_persist()
        if had_one:
            self._notify_listeners()
        return had_one

    def get_off_at(self, entity_id: str) -> datetime | None:
        """Return the scheduled off time for entity_id, or None if no timer is active."""

        return self._off_at.get(entity_id)

    def get_all_active(self) -> dict[str, datetime]:
        """Return a snapshot of every entity_id with a currently active timer and its off-at time."""

        return dict(self._off_at)

    @callback
    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a callback to be invoked whenever a timer is set, cancelled, or fires. Returns an unsubscribe function."""

        self._change_listeners.append(listener)

        @callback
        def _unsubscribe() -> None:
            self._change_listeners.remove(listener)

        return _unsubscribe

    def _notify_listeners(self) -> None:
        for listener in self._change_listeners:
            listener()

    @callback
    def notify_state_changed_externally(self, entity_id: str, *, is_on: bool) -> None:
        """
        Clear a pending timer if entity_id was turned off some other way.

        Called from light.py's update_state() on every state change - covers
        the light being turned off manually, from the Alarm.com app, or by
        any automation other than this manager's own scheduled turn-off.
        Without this, a stale auto_off_at attribute could linger on an
        already-off light until the original timer's moment arrived.
        """

        if not is_on and entity_id in self._off_at:
            self._cancel_existing(entity_id)
            self.hass.async_create_task(self._async_persist())
            self._notify_listeners()

    async def async_unload(self) -> None:
        """
        Cancel all pending in-memory listeners for this config entry.

        Deliberately does NOT clear persisted storage - a reload (as opposed
        to a full removal of the integration) should still honor timers set
        before the reload; async_load() will pick them back up.
        """

        for unsub in self._unsub.values():
            unsub()
        self._unsub.clear()

    def _schedule(self, entity_id: str, off_at: datetime) -> None:
        self._off_at[entity_id] = off_at

        async def _fire(_now: datetime) -> None:
            await self._async_fire(entity_id)

        self._unsub[entity_id] = async_track_point_in_time(self.hass, _fire, off_at)

    def _cancel_existing(self, entity_id: str) -> None:
        if unsub := self._unsub.pop(entity_id, None):
            unsub()
        self._off_at.pop(entity_id, None)

    async def _async_fire(self, entity_id: str) -> None:
        """Turn off entity_id, clear its tracked timer, and persist the change."""

        self._unsub.pop(entity_id, None)
        self._off_at.pop(entity_id, None)
        await self._async_persist()
        self._notify_listeners()
        await self.hass.services.async_call("light", "turn_off", {"entity_id": entity_id}, blocking=True)

    async def _async_persist(self) -> None:
        await self._store.async_save({entity_id: off_at.isoformat() for entity_id, off_at in self._off_at.items()})
