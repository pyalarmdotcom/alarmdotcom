"""Fixtures for alarmdotcom tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """
    Enable custom integrations for every test in this suite.

    Without this, Home Assistant's test harness ignores custom_components
    entirely (it only loads core integrations by default), so config flow
    and setup tests would silently no-op instead of exercising real code.
    """
    return


@pytest.fixture
def mock_system():
    """Build a minimal mock of the active Alarm.com system returned after login."""
    system = MagicMock()
    system.id = "12345"
    system.name = "Test System"
    return system


@pytest.fixture
def mock_bridge(mock_system):
    """
    Build a mock AlarmBridge representing a successful, no-OTP login.

    login() succeeds without raising, fetch_full_state() succeeds, and
    active_system / auth_controller.user_email are populated so
    async_step_final can build a title and unique_id without touching the
    real Alarm.com API.
    """
    bridge = MagicMock()
    bridge.login = AsyncMock(return_value=None)
    bridge.fetch_full_state = AsyncMock(return_value=None)
    bridge.active_system = mock_system
    bridge.auth_controller = MagicMock()
    bridge.auth_controller.user_email = "test@example.com"
    bridge.auth_controller.request_otp = AsyncMock(return_value=None)
    bridge.auth_controller.submit_otp = AsyncMock(return_value="mock-mfa-cookie")
    return bridge


@pytest.fixture
def mock_bridge_class(mock_bridge):
    """
    Patch AlarmBridge, as referenced in config_flow.py, to return mock_bridge.

    Patched where config_flow.py looks it up (its own `pyadc` alias), not
    where AlarmBridge is originally defined - this is the standard
    unittest.mock rule for patching imported names.
    """
    with patch(
        "custom_components.alarmdotcom.config_flow.pyadc.AlarmBridge",
        return_value=mock_bridge,
    ) as mock_cls:
        yield mock_cls


@pytest.fixture
def mock_setup_entry():
    """
    Prevent real integration setup (hub.py creates its own real AlarmBridge).

    Config flow tests should verify what the flow itself produces (form,
    errors, the created entry's data/unique_id) - not exercise the full
    runtime setup, which needs its own separate mocking (see test_init.py)
    to avoid making real network calls or leaving background tasks running
    after the test ends.
    """
    with patch(
        "custom_components.alarmdotcom.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
