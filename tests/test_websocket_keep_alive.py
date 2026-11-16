"""
Session keep-alive gating in the WebSocket client.

The event reader reports CONNECTED only for the very first connection and
RECONNECTED for every one after that, never returning to CONNECTED. A
keep-alive that only ran in the CONNECTED state therefore went silent for good
after the first reconnect, leaving the Alarm.com session to idle out.
"""

from __future__ import annotations

# isort: skip_file
# Import order matters here and must not be sorted: importing the component
# runs its sys.path shim, which puts the vendored library on sys.path as
# top-level `_pyalarmdotcomajax` - the same name the vendored modules import
# each other by, and the name monkeypatch resolves below. Without it first,
# this module cannot be collected on its own.
import custom_components.alarmdotcom  # noqa: F401

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from _pyalarmdotcomajax.websocket.client import WebSocketClient, WebSocketState


def _client() -> WebSocketClient:
    """Build a client whose keep-alive can run without touching the network."""
    bridge = MagicMock()
    # Large enough that the first pass never reaches the session-refresh
    # branch, leaving is_logged_in() as the signal that a keep-alive was sent.
    bridge.auth_controller.session_refresh_interval_ms = 1_800_000
    bridge.auth_controller.enable_keep_alive = True
    bridge.is_logged_in = AsyncMock(return_value=True)

    return WebSocketClient(bridge)


async def _run_briefly(client: WebSocketClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Let _keep_alive run its loop, then stop it.

    The interval constant is patched rather than asyncio.sleep itself: the
    client module's `asyncio` is the real module, so patching sleep through it
    would patch it for the whole test session, not just this loop. It is
    shortened, not zeroed - the loop divides by it.
    """
    monkeypatch.setattr(
        "_pyalarmdotcomajax.websocket.client.KEEP_ALIVE_SIGNAL_INTERVAL_S", 0.001
    )

    task = asyncio.create_task(client._keep_alive())
    await asyncio.sleep(0.01)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize(
    "state",
    [WebSocketState.CONNECTED, WebSocketState.RECONNECTED],
)
@pytest.mark.asyncio
async def test_keep_alive_runs_while_connected(
    state: WebSocketState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both live states keep the session alive - RECONNECTED is the usual one."""
    client = _client()
    client._state = state

    await _run_briefly(client, monkeypatch)

    client._bridge.is_logged_in.assert_awaited()


@pytest.mark.parametrize(
    "state",
    [WebSocketState.DISCONNECTED, WebSocketState.CONNECTING, WebSocketState.DEAD],
)
@pytest.mark.asyncio
async def test_keep_alive_skips_while_not_connected(
    state: WebSocketState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is sent while there is no live connection to keep alive."""
    client = _client()
    client._state = state

    await _run_briefly(client, monkeypatch)

    client._bridge.is_logged_in.assert_not_awaited()
