"""Setup requests delivery before prompting, including single-method accounts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant import data_entry_flow

from custom_components.alarmdotcom.config_flow import pyadc


@pytest.mark.parametrize("method", [pyadc.OtpType.email, pyadc.OtpType.sms])
async def test_single_delivery_method_requests_code_before_prompt(hass, mock_bridge_class, mock_bridge, method):
    """Only authenticator apps may skip requesting delivery from Alarm.com."""
    mock_bridge.login.side_effect = pyadc.OtpRequired(enabled_2fa_methods=[method])
    result = await hass.config_entries.flow.async_init("alarmdotcom", context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "test@example.com", "password": "synthetic"},
    )
    assert result["step_id"] == "otp_select_method"
    mock_bridge.auth_controller.request_otp.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"otp_method": method.name})
    assert result["step_id"] == "otp_submit"
    mock_bridge.auth_controller.request_otp.assert_awaited_once_with(method)
    mock_bridge.auth_controller.submit_otp.assert_not_awaited()


@pytest.mark.parametrize("method", [pyadc.OtpType.email, pyadc.OtpType.sms])
async def test_delivery_request_failure_does_not_advance_to_code_prompt(hass, mock_bridge_class, mock_bridge, method):
    """A failed send request must not tell the user to enter an unsent code."""
    mock_bridge.login.side_effect = pyadc.OtpRequired(enabled_2fa_methods=[method])
    mock_bridge.auth_controller.request_otp.side_effect = TimeoutError()
    result = await hass.config_entries.flow.async_init("alarmdotcom", context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "test@example.com", "password": "synthetic"},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"otp_method": method.name})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "otp_select_method"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(("method", "action"), [
    (pyadc.OtpType.sms, "sendTwoFactorAuthenticationCodeViaSms"),
    (pyadc.OtpType.email, "sendTwoFactorAuthenticationCodeViaEmail"),
])
async def test_real_delivery_controller_posts_the_selected_method(method, action):
    """Verify the actual library action, beyond a mocked setup flow."""
    bridge = pyadc.AlarmBridge("user", "synthetic")
    bridge.post = AsyncMock()
    bridge.auth_controller._identities._resources = {"identity": SimpleNamespace(id="identity")}
    await bridge.auth_controller.request_otp(method)
    bridge.post.assert_awaited_once_with(
        path="engines/twoFactorAuthentication/twoFactorAuthentications",
        id="identity", action=action, mini_response=True,
    )
