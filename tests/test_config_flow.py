"""
Tests for the alarmdotcom config flow.

Covers the Bronze quality-scale "config-flow-test-coverage" requirement:
the initial login step, all three login failure modes shown to the user
(cannot_connect, invalid_auth, unknown), the OTP method-selection step
(including the auto-skip-when-only-app-is-enabled case), OTP submission
(including the invalid-code case), duplicate-entry abort, and the options
flow's two steps.
"""

from unittest.mock import AsyncMock

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.alarmdotcom._pyalarmdotcomajax as pyadc
from custom_components.alarmdotcom.const import (
    CONF_ARM_AWAY,
    CONF_ARM_CODE,
    CONF_ARM_HOME,
    CONF_ARM_NIGHT,
    CONF_CAMERA_TOKEN_REFRESH_INTERVAL,
    CONF_OPTIONS_DEFAULT,
    CONF_OTP,
    CONF_OTP_METHOD,
    CONF_REMOVE_ARM_CODE,
    DOMAIN,
)

VALID_CREDS = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "hunter2"}


async def _start_user_flow(hass: HomeAssistant) -> dict:
    """Kick off the config flow and land on the initial user step."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """The first thing a user sees is the username/password form."""
    result = await _start_user_flow(hass)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_full_flow_success_no_otp(
    hass: HomeAssistant, mock_bridge_class, mock_bridge, mock_setup_entry
) -> None:
    """A user without 2FA enabled logs in and gets a config entry immediately."""
    result = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_CREDS
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test System (test@example.com)"
    assert result["data"][CONF_USERNAME] == VALID_CREDS[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == VALID_CREDS[CONF_PASSWORD]

    # Unique ID should be the Alarm.com system ID, not something derived
    # from the username - this is what prevents a user from accidentally
    # adding the same system twice under two different login attempts.
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == "12345"


@pytest.mark.parametrize(
    ("login_side_effect", "expected_error"),
    [
        (TimeoutError(), "cannot_connect"),
        (pyadc.UnexpectedResponse("boom"), "cannot_connect"),
        (pyadc.NotAuthorized(), "cannot_connect"),
        (pyadc.AuthenticationFailed(), "invalid_auth"),
        (ValueError("something unrelated broke"), "unknown"),
    ],
)
async def test_login_failure_modes(
    hass: HomeAssistant, mock_bridge_class, mock_bridge, login_side_effect, expected_error
) -> None:
    """
    Every distinct login failure should surface its own specific error to the user.

    This matters because #21 (OTP "Failed to Connect") existed specifically
    because a different failure was being reported as cannot_connect -
    asserting each exception maps to its own error code, not just "some
    error happened", is what would have caught that class of regression.
    """
    mock_bridge.login = AsyncMock(side_effect=login_side_effect)

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_CREDS
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


async def test_must_configure_mfa_aborts(hass: HomeAssistant, mock_bridge_class, mock_bridge) -> None:
    """If Alarm.com requires 2FA to be enabled account-wide, abort with a clear reason."""
    mock_bridge.login = AsyncMock(side_effect=pyadc.MustConfigureMfa())

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_CREDS
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "must_enable_2fa"


async def test_otp_flow_with_method_selection(
    hass: HomeAssistant, mock_bridge_class, mock_bridge, mock_setup_entry
) -> None:
    """A user with SMS + email 2FA enabled sees a method picker, then an OTP prompt."""
    mock_bridge.login = AsyncMock(
        side_effect=pyadc.OtpRequired(enabled_2fa_methods=[pyadc.OtpType.sms, pyadc.OtpType.email])
    )

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_CREDS
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "otp_select_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OTP_METHOD: "sms"}
    )

    mock_bridge.auth_controller.request_otp.assert_awaited_once_with(pyadc.OtpType.sms)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "otp_submit"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OTP: "123456"}
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    mock_bridge.auth_controller.submit_otp.assert_awaited_once()


async def test_otp_flow_auto_skips_method_selection_for_app_only(
    hass: HomeAssistant, mock_bridge_class, mock_bridge, mock_setup_entry
) -> None:
    """
    If authenticator-app is the ONLY enabled method, skip straight to the OTP prompt.

    There's nothing to request for the app method (no SMS/email to trigger),
    so making the user pick from a list of one option is pure friction.
    """
    mock_bridge.login = AsyncMock(
        side_effect=pyadc.OtpRequired(enabled_2fa_methods=[pyadc.OtpType.app])
    )

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_CREDS
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "otp_app_submit"
    mock_bridge.auth_controller.request_otp.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OTP: "123456"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert mock_bridge.auth_controller.submit_otp.await_args.kwargs["method"] == pyadc.OtpType.app


async def test_invalid_otp_code_shows_error(
    hass: HomeAssistant, mock_bridge_class, mock_bridge
) -> None:
    """A wrong OTP code re-shows the form with an error, not a crash."""
    mock_bridge.login = AsyncMock(
        side_effect=pyadc.OtpRequired(enabled_2fa_methods=[pyadc.OtpType.app])
    )
    mock_bridge.auth_controller.submit_otp = AsyncMock(return_value=None)

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_CREDS
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OTP: "000000"}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "otp_app_submit"
    assert result["errors"] == {"base": "invalid_otp"}


async def test_duplicate_system_aborts(hass: HomeAssistant, mock_bridge_class, mock_bridge) -> None:
    """Logging into a system that's already configured should abort, not duplicate."""
    MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_CREDS).add_to_hass(hass)

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_CREDS
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_full_walkthrough(hass: HomeAssistant) -> None:
    """The options flow's three steps (arm code, arm mode profiles, then polling intervals) all work."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_CREDS)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_ARM_CODE: "1234", CONF_REMOVE_ARM_CODE: False},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "modes"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_ARM_HOME: ["silent_arming"], CONF_ARM_AWAY: [], CONF_ARM_NIGHT: []},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "polling"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"activity_poll_interval": 15, "full_state_poll_interval": 5},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ARM_CODE] == "1234"
    assert result["data"][CONF_ARM_HOME] == ["silent_arming"]
    assert result["data"]["activity_poll_interval"] == 15
    assert result["data"]["full_state_poll_interval"] == 5


async def test_options_flow_polling_step_accepts_custom_intervals(hass: HomeAssistant) -> None:
    """The polling step actually persists custom (non-default) interval values, not just the defaults."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_CREDS)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ARM_CODE: "", CONF_REMOVE_ARM_CODE: False}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ARM_HOME: [], CONF_ARM_AWAY: [], CONF_ARM_NIGHT: []}
    )
    assert result["step_id"] == "polling"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"activity_poll_interval": 60, "full_state_poll_interval": 15},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["activity_poll_interval"] == 60
    assert result["data"]["full_state_poll_interval"] == 15


async def test_options_flow_polling_step_persists_camera_token_refresh(hass: HomeAssistant) -> None:
    """The camera token refresh interval (#93) is set on the polling step and persisted."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_CREDS)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"arm_code": "", "remove_arm_code": False}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"arm_home_options": [], "arm_away_options": [], "arm_night_options": []},
    )
    assert result["step_id"] == "polling"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "activity_poll_interval": 15,
            "full_state_poll_interval": 5,
            "camera_token_refresh_interval": 10,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["camera_token_refresh_interval"] == 10


def test_camera_token_refresh_default_is_the_previously_hardcoded_thirty_minutes() -> None:
    """Existing installs must keep the 30-minute cadence they had before this was an option."""
    assert CONF_OPTIONS_DEFAULT[CONF_CAMERA_TOKEN_REFRESH_INTERVAL] == 30


@pytest.mark.parametrize("method", [pyadc.OtpType.sms, pyadc.OtpType.email])
async def test_resend_code_does_not_submit_otp(
    hass, mock_bridge_class, mock_bridge, mock_setup_entry, method,
):
    """Request another delivery without a code, then finish using the new code."""
    mock_bridge.login = AsyncMock(side_effect=pyadc.OtpRequired(enabled_2fa_methods=[method]))
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], VALID_CREDS)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_OTP_METHOD: method.name})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"resend_code": True})
    assert result["step_id"] == "otp_submit"
    assert result["errors"] == {}
    assert "new code" in result["description_placeholders"]["resend_status"]
    assert mock_bridge.auth_controller.request_otp.await_count == 2
    mock_bridge.auth_controller.submit_otp.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_OTP: "123456"})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_resend_failure_remains_on_code_form(hass, mock_bridge_class, mock_bridge):
    """An unsuccessful resend must not claim success or discard the login flow."""
    mock_bridge.login = AsyncMock(side_effect=pyadc.OtpRequired(enabled_2fa_methods=[pyadc.OtpType.sms]))
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], VALID_CREDS)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_OTP_METHOD: "sms"})
    mock_bridge.auth_controller.request_otp.side_effect = TimeoutError()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"resend_code": True})
    assert result["step_id"] == "otp_submit"
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"]["resend_status"] == ""
    mock_bridge.auth_controller.submit_otp.assert_not_awaited()


async def test_app_otp_has_no_resend_control(hass, mock_bridge_class, mock_bridge):
    """App codes are generated locally and must not offer an SMS/email request."""
    mock_bridge.login = AsyncMock(side_effect=pyadc.OtpRequired(enabled_2fa_methods=[pyadc.OtpType.app]))
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], VALID_CREDS)
    assert "resend_code" not in result["data_schema"].schema
    mock_bridge.auth_controller.request_otp.assert_not_awaited()


async def test_camera_transport_option_is_offered_and_persisted(hass: HomeAssistant) -> None:
    """The options UI restores endToEnd by default and offers Janus without code edits."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_CREDS)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_REMOVE_ARM_CODE: False},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ARM_HOME: [], CONF_ARM_AWAY: [], CONF_ARM_NIGHT: []},
    )
    schema = result["data_schema"]
    defaults = schema({"activity_poll_interval": 15, "full_state_poll_interval": 5})
    assert defaults["camera_stream_transport"] == "endToEnd"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**defaults, "camera_stream_transport": "janus"},
    )
    assert result["data"]["camera_stream_transport"] == "janus"
