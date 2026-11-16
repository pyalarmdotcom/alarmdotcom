"""
Tests for alarmdotcom's __init__.py: entry setup, auth-failure handling, and unload.

Contributes toward the Silver quality-scale "test-coverage" requirement.
This isn't full coverage of every code path in __init__.py (the camera
session and debug-event handlers aren't covered here) - it's the core
setup/teardown lifecycle, which is the highest-value part to get right.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.alarmdotcom._pyalarmdotcomajax as pyadc
from custom_components.alarmdotcom.const import DOMAIN

VALID_DATA = {"username": "test@example.com", "password": "hunter2"}


@pytest.fixture
def mock_hub(hass: HomeAssistant):
    """Build a mock AlarmHub that initializes successfully with no real network calls."""
    hub = MagicMock()
    hub.initialize = AsyncMock(return_value=True)
    hub.close = AsyncMock(return_value=True)
    hub.api = MagicMock()
    hub.api.locks = []
    hub.hass = hass
    hub.config_entry.options = {}
    return hub


@pytest.fixture
def mock_camera_session():
    """Build a mock camera session that skips real login."""
    session = MagicMock()
    session.owns_session = False
    session.ajax_key = "mock-ajax-key"
    session.login = AsyncMock(return_value=None)
    session.close = AsyncMock(return_value=None)
    return session


async def test_setup_entry_success(
    hass: HomeAssistant, mock_hub, mock_camera_session
) -> None:
    """A healthy setup: hub initializes, platforms load, entry ends up LOADED."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_DATA)
    entry.add_to_hass(hass)

    with (
        patch("custom_components.alarmdotcom.AlarmHub", return_value=mock_hub),
        patch(
            "custom_components.alarmdotcom.AlarmCameraSession.from_alarm_bridge",
            return_value=mock_camera_session,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert entry.state == ConfigEntryState.LOADED
    mock_hub.initialize.assert_awaited_once()


async def test_setup_entry_auth_failure_triggers_reauth(
    hass: HomeAssistant, mock_hub
) -> None:
    """
    If the hub can't authenticate, the entry should end up needing reauth.

    hub.initialize() raising an AuthenticationException should map to
    ConfigEntryAuthFailed, which HA surfaces as SETUP_ERROR with a reauth
    flow available - not a generic setup failure that gives the user no
    path forward.
    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_DATA)
    entry.add_to_hass(hass)

    mock_hub.initialize = AsyncMock(side_effect=pyadc.AuthenticationFailed())

    with patch("custom_components.alarmdotcom.AlarmHub", return_value=mock_hub):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connection_failure_retries(
    hass: HomeAssistant, mock_hub
) -> None:
    """
    A transient connection failure should be retryable, not a hard failure.

    This maps to ConfigEntryNotReady, which HA retries automatically -
    important for e.g. Alarm.com being briefly unreachable at HA startup,
    which shouldn't require the user to manually reload the integration.
    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_DATA)
    entry.add_to_hass(hass)

    mock_hub.initialize = AsyncMock(side_effect=TimeoutError())

    with patch("custom_components.alarmdotcom.AlarmHub", return_value=mock_hub):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_unload_entry_closes_hub_and_camera_session(
    hass: HomeAssistant, mock_hub, mock_camera_session
) -> None:
    """Unloading should close both the hub and the camera session, not leak either."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_DATA)
    entry.add_to_hass(hass)

    with (
        patch("custom_components.alarmdotcom.AlarmHub", return_value=mock_hub),
        patch(
            "custom_components.alarmdotcom.AlarmCameraSession.from_alarm_bridge",
            return_value=mock_camera_session,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            return_value=True,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    mock_hub.close.assert_awaited_once()
    mock_camera_session.close.assert_awaited_once()
