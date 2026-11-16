"""Controller interfaces with the Alarm.com API via pyalarmdotcomajax."""

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any

import _pyalarmdotcomajax as pyadc
import aiohttp
from _pyalarmdotcomajax import AlarmBridge
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_FULL_STATE_POLL_INTERVAL,
    CONF_MFA_TOKEN,
    CONF_OPTIONS_DEFAULT,
    DOMAIN,
    PLATFORMS,
)

log = logging.getLogger(__name__)

# Default full-state poll interval (minutes), used until a user configures
# their own via the options flow (see config_flow.py's
# ADCOptionsFlowHandler.async_step_polling) - a safety net against missed
# websocket events, not this integration's primary source of state.
DEFAULT_POLLING_INTERVAL_MINUTES = CONF_OPTIONS_DEFAULT[CONF_FULL_STATE_POLL_INTERVAL]

# Reconnect backoff: wait this long before reloading after a websocket death
WS_RECONNECT_DELAY = 30  # seconds
WS_MAX_RECONNECT_ATTEMPTS = 5
# A refresh that fails with an authentication error reconnects, which logs in again. A refresh that keeps failing that
# way after a successful login would otherwise log in every few minutes; each login also signs the account's browser
# sessions out. Between two such reconnects the periodic refresh simply tries again later.
REFRESH_AUTH_RECONNECT_MIN_INTERVAL_S = 10 * 60

WS_HEARTBEAT_INTERVAL = 60  # seconds


class _AlarmBridgeWithHeartbeat(AlarmBridge):
    """
    AlarmBridge subclass that injects a WebSocket heartbeat.

    aiohttp will send a PING frame every WS_HEARTBEAT_INTERVAL seconds and
    close the connection if no PONG is received, triggering reconnection.
    This catches silent drops that the library's HTTP-based keep-alive misses.
    """

    @contextlib.asynccontextmanager
    async def ws_connect(self, url: str, **kwargs: Any) -> AsyncIterator[aiohttp.ClientWebSocketResponse]:
        if self._websession is None:
            raise pyadc.NotInitialized(
                "Cannot initiate WebSocket connection without an existing session."
            )
        kwargs.setdefault("heartbeat", WS_HEARTBEAT_INTERVAL)
        async with self._websession.ws_connect(url, **kwargs) as res:
            yield res


class AlarmHub:
    """Config-entry initiated Alarm Hub."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        self.hass: HomeAssistant = hass
        self.config_entry: ConfigEntry = config_entry

        self.api = _AlarmBridgeWithHeartbeat(
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            mfa_token=config_entry.data.get(CONF_MFA_TOKEN),
        )

        self.close_jobs: list[CALLBACK_TYPE] = []
        self.available: bool = True
        self._refresh_auth_failed = False
        self._ws_dead = False
        self._reconnect_attempts: int = 0
        self._reconnect_task: asyncio.Task | None = None
        self._refresh_lock = asyncio.Lock()
        self._last_refresh_auth_reconnect: float | None = None

    async def login(self) -> bool:
        """Log in to alarm.com."""
        try:
            await self.api.login()
        except pyadc.AuthenticationFailed as err:
            raise ConfigEntryAuthFailed from err
        except pyadc.MustConfigureMfa:
            log.error(
                "Alarm.com requires that two-factor authentication be set up on your account. "
                "Please log in to Alarm.com and set up two-factor authentication."
            )
            return False
        except Exception as err:
            log.error("Unexpected error during Alarm.com login: %s", err)
            return False

        return True

    async def initialize(self) -> bool:
        """Initialize connection to Alarm.com."""
        setup_ok = False

        try:
            async with asyncio.timeout(10):
                await self.api.initialize()
            setup_ok = True
        except (
            TimeoutError,
            pyadc.UnexpectedResponse,
            pyadc.ServiceUnavailable,
        ) as err:
            raise ConfigEntryNotReady("Could not connect to Alarm.com.") from err
        except pyadc.AuthenticationException as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            # Returning False here left the entry "Loaded" with no websocket, no periodic refresh and no retry
            # (async_setup_entry ignores the return value). Not-ready makes Home Assistant retry setup with backoff,
            # which is what a dropped connection or DNS failure during a reboot needs.
            log.exception("Unexpected error during Alarm.com initialization.")
            raise ConfigEntryNotReady("Unexpected error while connecting to Alarm.com.") from err
        finally:
            if not setup_ok:
                log.debug("Closing Alarm.com session because entry setup did not complete.")
                await self.api.close()

        await self.api.start_event_monitoring(self._ws_state_handler)

        self.close_jobs.append(
            self.api.events.subscribe(pyadc.EventBrokerTopic.RESOURCE_DELETED, self._remove_deleted_device)
        )

        # Periodic full state refresh as a safety net for missed websocket events
        full_state_interval_minutes = self.config_entry.options.get(
            CONF_FULL_STATE_POLL_INTERVAL, DEFAULT_POLLING_INTERVAL_MINUTES
        )
        self.close_jobs.append(
            async_track_time_interval(
                self.hass,
                self._async_refresh_state,
                timedelta(minutes=full_state_interval_minutes),
            )
        )

        self.close_jobs.append(self.config_entry.add_update_listener(_update_listener))

        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, str(self.api.active_system.id))},
            manufacturer="Alarm.com",
            name=self.api.active_system.name,
            entry_type=dr.DeviceEntryType.SERVICE,
            model="Security System",
        )

        self._reconnect_attempts = 0
        return True

    @callback
    def _remove_deleted_device(self, message: pyadc.EventBrokerMessage) -> None:
        """
        Remove a device Alarm.com no longer lists, together with every entity on it.

        Only the device's main entity removed itself before. Its trouble, malfunction, battery and debug entities
        stayed behind, and the ones still subscribed to the vanished resource raised on every connection event.
        A delete only arrives after several refreshes in a row without the device (MISSING_REFRESHES_BEFORE_REMOVAL).
        """
        if not isinstance(message, pyadc.ResourceEventMessage):
            return

        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device_by_identifier((DOMAIN, message.id), self.config_entry.entry_id)
        if device is None or device.entry_type == dr.DeviceEntryType.SERVICE:
            return

        log.info("Alarm.com no longer lists %s; removing device %s.", message.id, device.name_by_user or device.name)
        device_registry.async_remove_device(device.id)

    @callback
    def _update_availability(self) -> None:
        """Publish changes from HTTP health as well as the event connection."""
        available = not (self._refresh_auth_failed or self._ws_dead)
        if available != self.available:
            self.available = available
            self.api.events.publish(
                pyadc.EventBrokerMessage(topic=pyadc.EventBrokerTopic.CONNECTION_EVENT)
            )

    async def _async_refresh_state(self, _now: datetime | None = None) -> None:
        """Periodically poll full state as a safety net against missed websocket events."""
        try:
            log.debug("Alarm.com: performing periodic full state refresh.")
            # NOTE: fetch_full_state() routes through each resource controller's initialize(),
            # which no-ops after the very first call (see pyalarmdotcomajax#22 discussion / hub
            # bug found while investigating ha-alarmdotcom#42). refresh_all_resources() instead
            # calls each controller's _refresh() directly, the same mechanism used when the
            # WebSocket reconnects, so it actually re-fetches and re-publishes state every time
            # this runs instead of being a silent no-op.
            async with self._refresh_lock:
                await self.api.refresh_all_resources()
                self._refresh_auth_failed = False
                self._update_availability()
        except pyadc.NotAuthorized as err:
            # 406/423: an endpoint this account may not use. The session is fine, so logging in again cannot help.
            log.debug("Alarm.com: periodic refresh refused by Alarm.com: %s", err)
        except pyadc.AuthenticationException:
            self._refresh_auth_failed = True
            self._update_availability()
            now = time.monotonic()
            if (
                self._last_refresh_auth_reconnect is not None
                and now - self._last_refresh_auth_reconnect < REFRESH_AUTH_RECONNECT_MIN_INTERVAL_S
            ):
                log.warning(
                    "Alarm.com: periodic refresh failed — auth error again soon after reconnecting. "
                    "Not logging in again yet; the next refresh will retry."
                )
                return
            self._last_refresh_auth_reconnect = now
            log.warning("Alarm.com: periodic refresh failed — auth error. Will attempt reconnect.")
            await self._async_handle_ws_death()
        except Exception as err:
            log.warning("Alarm.com: periodic refresh failed: %s", err)

    async def _ws_state_handler(self, message: pyadc.EventBrokerMessage) -> None:
        """Handle websocket state changes with automatic reconnect."""
        if not isinstance(message, pyadc.ConnectionEvent):
            return

        if message.current_state == pyadc.WebSocketState.DEAD:
            log.warning(
                "Alarm.com websocket died. Will attempt reconnect in %s seconds (attempt %d/%d).",
                WS_RECONNECT_DELAY,
                self._reconnect_attempts + 1,
                WS_MAX_RECONNECT_ATTEMPTS,
            )
            self._ws_dead = True
            self._update_availability()
            await self._async_handle_ws_death()

        elif message.current_state in (pyadc.WebSocketState.CONNECTED, pyadc.WebSocketState.RECONNECTED):
            was_dead = self._ws_dead
            if was_dead:
                log.info("Alarm.com websocket reconnected. Reconciling device state.")
            self._ws_dead = False
            self._update_availability()
            self._reconnect_attempts = 0
            if was_dead:
                self.hass.async_create_task(self._async_refresh_state())

        elif message.current_state not in (
            pyadc.WebSocketState.CONNECTED,
            pyadc.WebSocketState.CONNECTING,
        ):
            log.info("Alarm.com websocket state: %s", message.current_state)

        log.debug("Alarm.com websocket state: %s", message.current_state)

    async def _async_handle_ws_death(self) -> None:
        """Schedule a reconnect attempt with backoff. Reloads the entry if all attempts fail."""
        if self._reconnect_task and not self._reconnect_task.done():
            return  # Already a reconnect in progress

        self._reconnect_task = self.hass.async_create_task(
            self._async_reconnect_with_backoff()
        )

    async def _async_reconnect_with_backoff(self) -> None:
        """Attempt to reconnect with exponential backoff, then reload entry if exhausted."""
        while self._reconnect_attempts < WS_MAX_RECONNECT_ATTEMPTS:
            self._reconnect_attempts += 1
            delay = WS_RECONNECT_DELAY * self._reconnect_attempts
            log.info(
                "Alarm.com: reconnect attempt %d/%d in %d seconds...",
                self._reconnect_attempts,
                WS_MAX_RECONNECT_ATTEMPTS,
                delay,
            )
            await asyncio.sleep(delay)

            try:
                log.debug("Closing Alarm.com session before reconnect attempt %d.", self._reconnect_attempts)
                await self.api.close()
                async with asyncio.timeout(15):
                    await self.api.initialize()
                await self.api.start_event_monitoring(self._ws_state_handler)
            except pyadc.AuthenticationException:
                log.error("Alarm.com: reconnect failed — authentication error. Triggering reauth.")
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.config_entry.entry_id)
                )
                return
            except Exception as err:
                log.warning(
                    "Alarm.com: reconnect attempt %d failed: %s",
                    self._reconnect_attempts,
                    err,
                )
            else:
                self._ws_dead = False
                self._update_availability()
                self._reconnect_attempts = 0
                log.info("Alarm.com: reconnect successful.")
                # initialize() skips controllers that are already set up, so nothing above re-fetched state.
                # Anything that changed while disconnected would otherwise wait for the next periodic refresh.
                await self._async_refresh_state()
                return

        # All attempts exhausted — schedule a full entry reload.
        # async_schedule_reload is a sync @callback that already schedules its
        # own task internally (it returns None) - wrapping it in
        # async_create_task() would pass None where a coroutine is expected,
        # raising TypeError immediately after the reload had already fired as
        # a side effect. Call it directly.
        log.error(
            "Alarm.com: all %d reconnect attempts failed. Scheduling integration reload.",
            WS_MAX_RECONNECT_ATTEMPTS,
        )
        self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    async def close(self) -> bool:
        """Close the hub and unload platforms."""
        # Cancel any in-progress reconnect
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task

        while self.close_jobs:
            self.close_jobs.pop()()

        log.debug("Closing Alarm.com session because Home Assistant is unloading the entry.")
        await self.api.close()

        unload_success: bool = await self.hass.config_entries.async_unload_platforms(
            self.config_entry,
            PLATFORMS,
        )

        return unload_success


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle ConfigEntry options update."""
    await hass.config_entries.async_reload(entry.entry_id)
