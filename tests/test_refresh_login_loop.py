"""
A refused endpoint is not a login failure, and the periodic refresh cannot drive a login loop.

Seen on 2026-10-14/15: from 22:56 the 5-minute refresh failed every couple of minutes with an "auth error" (284 times
in 12 hours). Alarm.com was answering one controller's request with 423, which the request layer raises as
NotAuthorized, a subclass of AuthenticationException. refresh_all_resources passed it up as an authentication failure,
the hub reconnected (logging in again, which also signs the account's browser sessions out), refreshed again, got the
same 423, and so on. The websocket kept delivering events, so nothing looked wrong in Home Assistant.
"""

# Importing the component runs its sys.path shim, which must happen before the bare `_pyalarmdotcomajax`
# imports below resolve; see test_sensor_websocket_state.
import custom_components.alarmdotcom  # noqa: F401, I001

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from _pyalarmdotcomajax import AlarmBridge, ConnectionEvent, EventBrokerTopic, WebSocketState
from _pyalarmdotcomajax.exceptions import AuthenticationFailed, NotAuthorized

from custom_components.alarmdotcom import hub as hub_module
from custom_components.alarmdotcom.hub import AlarmHub


def _controller(error: Exception | None) -> SimpleNamespace:
    return SimpleNamespace(initialized=True, _refresh=AsyncMock(side_effect=error))


async def test_a_refused_endpoint_does_not_look_like_a_login_failure() -> None:
    """406/423 means this account cannot use one endpoint; the other controllers still refresh."""
    healthy = _controller(None)
    bridge = SimpleNamespace(resource_controllers=[_controller(NotAuthorized("423")), healthy])

    await AlarmBridge.refresh_all_resources(bridge)  # type: ignore[arg-type]

    healthy._refresh.assert_awaited_once()


async def test_a_rejected_session_still_reaches_the_hub() -> None:
    """A real authentication failure is how the hub learns it has to log in again."""
    bridge = SimpleNamespace(resource_controllers=[_controller(AuthenticationFailed("401")), _controller(None)])

    with pytest.raises(AuthenticationFailed):
        await AlarmBridge.refresh_all_resources(bridge)  # type: ignore[arg-type]


def _hub(refresh_error: Exception) -> AlarmHub:
    entry = MagicMock()
    entry.data = {"username": "u", "password": "p"}
    entry.options = {}
    entry.entry_id = "e"
    hub = AlarmHub(MagicMock(data={}), entry)
    hub.api.refresh_all_resources = AsyncMock(side_effect=refresh_error)  # type: ignore[method-assign]
    hub._async_handle_ws_death = AsyncMock()  # type: ignore[method-assign]
    return hub


async def test_the_hub_does_not_reconnect_for_a_refused_endpoint() -> None:
    """Defence in depth, in case NotAuthorized reaches the hub some other way."""
    hub = _hub(NotAuthorized("423"))

    await hub._async_refresh_state()

    hub._async_handle_ws_death.assert_not_awaited()


async def test_repeated_refresh_auth_errors_log_in_at_most_once_per_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even a genuine, persistent auth error must not turn every refresh into a fresh login."""
    clock = [1000.0]
    monkeypatch.setattr(hub_module.time, "monotonic", lambda: clock[0])
    hub = _hub(AuthenticationFailed("401"))

    await hub._async_refresh_state()
    clock[0] += 150
    await hub._async_refresh_state()
    clock[0] += 150
    await hub._async_refresh_state()
    assert hub._async_handle_ws_death.await_count == 1

    clock[0] += hub_module.REFRESH_AUTH_RECONNECT_MIN_INTERVAL_S
    await hub._async_refresh_state()
    assert hub._async_handle_ws_death.await_count == 2


async def test_a_device_type_the_system_does_not_have_is_not_requested() -> None:
    """Image sensors: none on this system, and asking anyway is what earned the 423 every five minutes."""
    from _pyalarmdotcomajax.controllers.image_sensors import ImageSensorController  # noqa: PLC0415
    from _pyalarmdotcomajax.events import EventBroker  # noqa: PLC0415

    bridge = MagicMock()
    bridge.events = EventBroker()
    bridge.get = AsyncMock()
    controller = ImageSensorController(bridge)  # type: ignore[arg-type]

    await controller.initialize(target_device_ids=[])
    await controller._refresh()

    assert controller.initialized
    bridge.get.assert_not_awaited()


async def test_websocket_connection_does_not_hide_failed_http_refresh() -> None:
    """Entities recover only when Alarm.com accepts a subsequent full refresh."""
    hub = _hub(AuthenticationFailed("403"))
    availability = []
    hub.api.events.subscribe(EventBrokerTopic.CONNECTION_EVENT, lambda _: availability.append(hub.available))

    await hub._async_refresh_state()
    await hub._ws_state_handler(ConnectionEvent(current_state=WebSocketState.CONNECTED, next_attempt_s=None))
    assert availability == [False]
    assert not hub.available

    hub.api.refresh_all_resources.side_effect = None
    await hub._async_refresh_state()
    assert availability == [False, True]
