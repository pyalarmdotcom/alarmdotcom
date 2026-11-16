"""Camera token refresh cadence follows the option (#93)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

# homeassistant.components.camera imports PyTurboJPEG at module level, and the
# test helper does not install component requirements. Skip rather than fail
# where it is absent; the options-flow tests still cover the option itself.
pytest.importorskip("turbojpeg")

from custom_components.alarmdotcom.camera import AlarmDotComCamera, async_setup_entry
from custom_components.alarmdotcom.const import DOMAIN


def _session_with_one_camera() -> MagicMock:
    session = MagicMock()
    session.session_generation = 1
    session.get_camera_list = AsyncMock(return_value=[{"id": "cam-1", "description": "Porch"}])
    return session


async def _setup(hass: HomeAssistant, options: dict) -> list[AlarmDotComCamera]:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=options, title="Alarm.com")
    entry.add_to_hass(hass)
    entry.runtime_data = MagicMock(camera_session=_session_with_one_camera())
    added: list[AlarmDotComCamera] = []
    await async_setup_entry(hass, entry, added.extend)
    return added


async def test_setup_passes_the_configured_interval_to_each_camera(hass: HomeAssistant) -> None:
    """A user who set 10 minutes gets a 10-minute refresh."""
    (camera,) = await _setup(hass, {"camera_token_refresh_interval": 10})
    assert camera._token_refresh_interval == timedelta(minutes=10)


async def test_setup_falls_back_to_thirty_minutes_when_unset(hass: HomeAssistant) -> None:
    """An entry configured before this option existed keeps the old hardcoded cadence."""
    (camera,) = await _setup(hass, {})
    assert camera._token_refresh_interval == timedelta(minutes=30)


async def test_browser_reconnect_fetches_new_credentials(hass: HomeAssistant) -> None:
    """A cached stream token must not satisfy a new browser session."""
    (camera,) = await _setup(hass, {})
    camera.async_write_ha_state = MagicMock()
    camera._webrtc_config = {"cameraAuthToken": "synthetic-expired"}
    camera._session.get_stream_info = AsyncMock(side_effect=[
        {"cameraAuthToken": "synthetic-first"},
        {"cameraAuthToken": "synthetic-second"},
    ])
    assert await camera.async_get_webrtc_config() == {"cameraAuthToken": "synthetic-first"}
    assert await camera.async_get_webrtc_config() == {"cameraAuthToken": "synthetic-second"}
    assert camera._session.get_stream_info.await_count == 2
    assert camera.extra_state_attributes == {}


async def test_concurrent_browser_requests_wait_for_current_fetch(hass: HomeAssistant) -> None:
    """Neither caller receives the previous token while a refresh is pending."""
    (camera,) = await _setup(hass, {})
    camera.async_write_ha_state = MagicMock()
    camera._webrtc_config = {"cameraAuthToken": "synthetic-expired"}
    started = asyncio.Event()
    release = asyncio.Event()
    fresh = {"cameraAuthToken": "synthetic-fresh"}

    async def fetch(_camera_id: str, *, preferred_transport: str = "endToEnd") -> dict:
        started.set()
        await release.wait()
        return fresh

    camera._session.get_stream_info = AsyncMock(side_effect=fetch)
    first = asyncio.create_task(camera.async_get_webrtc_config())
    await started.wait()
    second = asyncio.create_task(camera.async_get_webrtc_config())
    await asyncio.sleep(0)
    assert not second.done()
    release.set()
    assert await asyncio.gather(first, second) == [fresh, fresh]
    camera._session.get_stream_info.assert_awaited_once_with("cam-1", preferred_transport="endToEnd")


@pytest.mark.parametrize("result", [None, RuntimeError("synthetic-failure")])
async def test_failed_reconnect_does_not_return_old_credentials(hass: HomeAssistant, result: object) -> None:
    """A failed refresh reports unavailable instead of replaying cached tokens."""
    (camera,) = await _setup(hass, {})
    camera.async_write_ha_state = MagicMock()
    camera._webrtc_config = {"cameraAuthToken": "synthetic-expired"}
    if isinstance(result, Exception):
        camera._session.get_stream_info = AsyncMock(side_effect=result)
    else:
        camera._session.get_stream_info = AsyncMock(return_value=result)
    assert await camera.async_get_webrtc_config() is None


async def test_setup_passes_explicit_janus_preference_to_camera(hass: HomeAssistant) -> None:
    """Accounts affected by #172 can select the working path through options."""
    (camera,) = await _setup(hass, {"camera_stream_transport": "janus"})
    camera.async_write_ha_state = MagicMock()
    camera._session.get_stream_info = AsyncMock(return_value={"streamType": "janus"})
    await camera.async_get_webrtc_config()
    camera._session.get_stream_info.assert_awaited_once_with("cam-1", preferred_transport="janus")
