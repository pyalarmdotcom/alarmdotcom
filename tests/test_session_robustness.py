"""
Session repair, login failures and reconnects for a 24/7 integration.

Each test covers a way the integration could stop working, lock the account, or keep reporting itself available
while nothing updated:

- a session repair deadlocking on its own lock;
- a failed login being retried by every request and poll;
- outages being reported as a wrong password;
- the websocket giving up for good after 25 failed reconnects;
- a network error during setup leaving the entry loaded with nothing running;
- a stalled websocket-token fetch hiding a gap in which events are lost.
"""

# Importing the component runs its sys.path shim, which must happen before the bare `_pyalarmdotcomajax`
# imports below resolve; see test_sensor_websocket_state.
import custom_components.alarmdotcom  # noqa: F401, I001

import asyncio
import contextlib
import json
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from _pyalarmdotcomajax import AlarmBridge
from _pyalarmdotcomajax.const import ResponseTypes
from _pyalarmdotcomajax.controllers import auth as auth_mod
from _pyalarmdotcomajax.exceptions import (
    AuthenticationException,
    AuthenticationFailed,
    OtpRequired,
    ServiceUnavailable,
)
from _pyalarmdotcomajax.models.auth import OtpType
from _pyalarmdotcomajax.websocket import client as ws_client
from _pyalarmdotcomajax.websocket.client import WebSocketClient, WebSocketState
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alarmdotcom.hub import AlarmHub

ERR401 = json.dumps({"errors": [{"status": "401", "code": "401"}]})


class FakeResp:
    """A response carrying only a body."""

    def __init__(self, body: str) -> None:
        """Hold the body."""
        self._body = body
        self.status = 200

    async def text(self) -> str:
        """Return the body."""
        return self._body

    def raise_for_status(self) -> None:
        """Never fail."""


def install_fake_http(bridge: AlarmBridge, responder: Callable[[str, str], str], calls: list) -> None:
    """Route every request through `responder`, recording (method, url, accept_types)."""

    @contextlib.asynccontextmanager
    async def fake_create_request(
        method: str, url: str, accept_types: Any = None, *, use_ajax_key: bool = True, **_kwargs: Any
    ) -> Any:
        calls.append((method, url, accept_types))
        await asyncio.sleep(0)
        yield FakeResp(responder(method, url))

    bridge.create_request = fake_create_request  # type: ignore[method-assign]


async def test_a_401_inside_the_repair_login_fails_instead_of_deadlocking() -> None:
    """
    The repair holds _login_lock while login() runs; a request inside login() must not try to repair again.

    It used to wait on the lock it already held, forever, and every later 401 queued behind it.
    """
    bridge = AlarmBridge("user", "pw")
    install_fake_http(bridge, lambda _m, _u: ERR401, [])

    auth = bridge.auth_controller
    auth._login_preload = AsyncMock(return_value={})  # type: ignore[method-assign]
    auth._login_submit_credentials = AsyncMock(return_value=None)  # type: ignore[method-assign]
    auth._identities.initialize = AsyncMock()  # type: ignore[method-assign]
    auth._profiles.initialize = AsyncMock()  # type: ignore[method-assign]
    auth._dealers.initialize = AsyncMock()  # type: ignore[method-assign]
    identity = MagicMock()
    identity.dealer_id = None
    identity.id = "ident-1"
    auth._identities._resources = {"ident-1": identity}

    with pytest.raises(AuthenticationException):
        async with asyncio.timeout(2):
            await bridge.get("websockets/token", None, mini_response=True)

    assert not bridge._login_lock.locked()


async def test_a_failed_repair_is_not_repeated_by_every_caller() -> None:
    """A rejected login is attempted once, then waits out a backoff that doubles on each failure."""
    bridge = AlarmBridge("user", "wrong-password")
    install_fake_http(bridge, lambda _m, _u: ERR401, [])

    logins = 0

    async def bad_password_login() -> None:
        nonlocal logins
        logins += 1
        await asyncio.sleep(0.01)
        raise AuthenticationFailed("bad password")

    bridge._auth_controller.login = bad_password_login  # type: ignore[method-assign]

    # Six controllers refreshing at once, then four activity polls: one login between them.
    results = await asyncio.gather(*[bridge.get("devices/sensors", None) for _ in range(6)], return_exceptions=True)
    for _ in range(4):
        with pytest.raises(AuthenticationFailed):
            await bridge.get("activity/activityDays", None)

    assert logins == 1
    assert all(isinstance(result, AuthenticationFailed) for result in results)

    # Once the backoff has passed, one more attempt, and the next wait is longer.
    first_backoff = bridge._login_backoff_s
    bridge._login_retry_at = 0.0
    with pytest.raises(AuthenticationFailed):
        await bridge.get("devices/sensors", None)

    assert logins == 2
    assert bridge._login_backoff_s == first_backoff * 2


async def test_a_successful_repair_resets_the_backoff() -> None:
    """A good login clears the failure, so the next expiry is repaired at once."""
    bridge = AlarmBridge("user", "pw")
    bodies = iter([ERR401, json.dumps({"value": "tok"})])
    install_fake_http(bridge, lambda _m, _u: next(bodies), [])
    bridge._auth_controller.login = AsyncMock(return_value=None)  # type: ignore[method-assign]
    bridge._record_login_failure(AuthenticationFailed("earlier"))
    bridge._login_retry_at = 0.0

    await bridge.get("websockets/token", None, mini_response=True)

    assert bridge._last_login_error is None
    assert bridge._login_backoff_s == 60


async def test_the_retry_after_a_repair_keeps_the_requested_response_type() -> None:
    """The token endpoint answers plain JSON; the retry used to ask for JSON:API."""
    bridge = AlarmBridge("user", "pw")
    calls: list = []
    bodies = iter([ERR401, json.dumps({"value": "tok"})])
    install_fake_http(bridge, lambda _m, _u: next(bodies), calls)
    bridge._auth_controller.login = AsyncMock(return_value=None)  # type: ignore[method-assign]

    await bridge.get("websockets/token", None, mini_response=True)

    assert [accept for _method, _url, accept in calls] == [ResponseTypes.JSON, ResponseTypes.JSON]


async def test_otp_required_during_a_repair_is_raised_as_such() -> None:
    """Only reauthentication can supply a one-time code; it used to look like a generic auth failure."""
    bridge = AlarmBridge("user", "pw")
    install_fake_http(bridge, lambda _m, _u: ERR401, [])
    bridge._auth_controller.login = AsyncMock(side_effect=OtpRequired([OtpType.sms]))  # type: ignore[method-assign]

    with pytest.raises(OtpRequired):
        await bridge.get("websockets/token", None, mini_response=True)


@pytest.mark.parametrize(
    "error",
    [
        aiohttp.ClientResponseError(MagicMock(), (), status=503),
        aiohttp.ServerDisconnectedError(),
    ],
)
async def test_an_outage_while_submitting_credentials_is_not_a_wrong_password(error: Exception) -> None:
    """An outage used to send Home Assistant to "reauthentication required", which it never retries."""
    bridge = AlarmBridge("user", "pw")
    attempts = 0

    @contextlib.asynccontextmanager
    async def failing_request(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal attempts
        attempts += 1
        raise error
        yield  # pragma: no cover

    bridge.create_request = failing_request  # type: ignore[method-assign]
    login_info = {
        auth_mod.VIEWSTATE_FIELD: "",
        auth_mod.VIEWSTATEGENERATOR_FIELD: "",
        auth_mod.EVENTVALIDATION_FIELD: "",
        auth_mod.PREVIOUSPAGE_FIELD: "",
    }

    with pytest.raises(ServiceUnavailable):
        await bridge.auth_controller._login_submit_credentials(login_info)

    assert attempts > 1


async def test_the_websocket_keeps_reconnecting_past_25_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """It used to stop for good after 25, with nothing to restart it."""
    monkeypatch.setattr(ws_client.random, "random", lambda: 0.0)  # no backoff in the test

    client = WebSocketClient(MagicMock())
    attempts_seen = asyncio.Event()

    async def failing_authenticate() -> None:
        if client._authenticate.await_count >= 40:  # type: ignore[attr-defined]
            attempts_seen.set()
        raise AuthenticationFailed("session repair failed")

    client._authenticate = AsyncMock(side_effect=failing_authenticate)  # type: ignore[method-assign]

    reader = asyncio.create_task(client._event_reader())
    async with asyncio.timeout(5):
        await attempts_seen.wait()

    assert not reader.done()
    reader.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await reader


@pytest.mark.parametrize("stage", ["token fetch", "handshake"])
async def test_a_stalled_rotation_takes_the_reconnect_path(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, stage: str
) -> None:
    """Report which stage stalled and reconnect after a failed planned rotation."""
    monkeypatch.setattr(ws_client, "WS_TOKEN_LIFETIME_S", 0.01)
    monkeypatch.setattr(ws_client, "WS_TOKEN_FETCH_TIMEOUT_S", 0.05)
    monkeypatch.setattr(ws_client, "WS_CONNECT_TIMEOUT_S", 0.05)
    caplog.set_level("DEBUG", logger=ws_client.__name__)
    monkeypatch.setattr(ws_client.random, "random", lambda: 0.0)

    bridge = MagicMock()
    token_calls = 0

    async def fake_get(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal token_calls
        token_calls += 1
        if token_calls == 2 and stage == "token fetch":
            await asyncio.sleep(3600)  # www.alarm.com stalls during the planned replacement
        response = MagicMock()
        response.value = "test-websocket-token"
        response.metadata = {"endpoint": "wss://webskt.example"}
        return response

    @contextlib.asynccontextmanager
    async def fake_ws_connect(_url: str, **_kwargs: Any) -> Any:
        if token_calls == 2 and stage == "handshake":
            await asyncio.sleep(3600)
        yield MagicMock(close_code=None)

    bridge.get = fake_get
    bridge.ws_connect = fake_ws_connect
    client = WebSocketClient(bridge)

    async def never_returns(_socket: object) -> None:
        await asyncio.sleep(3600)

    client._read_messages = never_returns  # type: ignore[method-assign]
    emitted: list[WebSocketState] = []
    client._emit_ws_state = lambda state, next_attempt_s=None: emitted.append(state)  # type: ignore[method-assign]

    reader = asyncio.create_task(client._event_reader())
    await asyncio.sleep(0.5)
    reader.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await reader
    pending = list(client._background_tasks)  # the delayed RECONNECTED emit
    client.stop()
    await asyncio.gather(*pending, return_exceptions=True)

    assert WebSocketState.DISCONNECTED in emitted
    assert token_calls >= 3  # gave up on the stalled attempt and connected again
    assert f"WebSocket {stage} failed after" in caplog.text
    assert "(TimeoutError)" in caplog.text
    assert "test-websocket-token" not in caplog.text
    assert "webskt.example" not in caplog.text


async def test_the_periodic_refresh_reports_auth_errors_to_the_hub(hass: HomeAssistant) -> None:
    """The refresh swallowed every exception, so the hub's reauth path never ran."""
    entry = MagicMock()
    entry.data = {"username": "u", "password": "p"}
    entry.entry_id = "e2"
    hub = AlarmHub(hass, entry)
    hub.api._systems._initialized = True
    hub.api._systems._refresh = AsyncMock(side_effect=AuthenticationFailed("expired"))  # type: ignore[method-assign]
    hub._async_handle_ws_death = AsyncMock()  # type: ignore[method-assign]

    await hub._async_refresh_state()

    hub._async_handle_ws_death.assert_awaited_once()


async def test_a_network_error_during_setup_is_retried(hass: HomeAssistant) -> None:
    """It used to leave the entry loaded with no websocket, no polling and no retry."""
    entry = MockConfigEntry(domain="alarmdotcom", unique_id="12345", data={"username": "u", "password": "p"})
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.alarmdotcom.hub._AlarmBridgeWithHeartbeat.initialize",
            AsyncMock(side_effect=aiohttp.ServerDisconnectedError()),
        ),
        patch(
            "custom_components.alarmdotcom.hub._AlarmBridgeWithHeartbeat.start_event_monitoring",
            AsyncMock(),
        ),
        patch(
            "custom_components.alarmdotcom.AlarmCameraSession.from_alarm_bridge",
            side_effect=RuntimeError("no cameras"),
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups", return_value=True),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.SETUP_RETRY

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
