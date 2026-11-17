"""Prevent sensitive Alarm.com request data leaking into logs or exceptions."""

import json
import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import _pyalarmdotcomajax.exceptions as adc_exceptions
import pytest

from custom_components.alarmdotcom._pyalarmdotcomajax import AlarmBridge
from custom_components.alarmdotcom.camera_api import _redact_stream_info

SECRETS = {
    "txtPassword": "fake-password-SECURITY-TEST",
    "otp": "fake-otp-SECURITY-TEST",
    "twoFactorAuthenticationId": "fake-mfa-SECURITY-TEST",
    "Cookie": "fake-session-SECURITY-TEST",
}


@pytest.mark.parametrize("error_code", [401, 403, 406, 409, 422, 423, 500])
@pytest.mark.asyncio
async def test_request_errors_never_expose_credentials(caplog, error_code):
    """Exercise real request error handling with synthetic secrets, without network access."""
    bridge = AlarmBridge()
    response = AsyncMock()
    response.text.return_value = json.dumps(
        {"errors": [{"code": str(error_code), "title": "Test failure"}]}
    )

    @asynccontextmanager
    async def fake_request(*args, **kwargs):
        yield response

    payload = {
        "txtPassword": SECRETS["txtPassword"],
        "code": SECRETS["otp"],
        "twoFactorAuthenticationId": SECRETS["twoFactorAuthenticationId"],
    }
    with (
        patch.object(bridge, "create_request", side_effect=fake_request),
        caplog.at_level(logging.DEBUG),
        pytest.raises(
            (adc_exceptions.AuthenticationFailed, adc_exceptions.NotAuthorized, adc_exceptions.UnexpectedResponse)
        ) as raised,
    ):
        await bridge.request(
            "POST",
            "https://www.alarm.com/web/api/test?token=fake-url-SECURITY-TEST",
            allow_login_repair=False,
            data=payload,
            headers={"Cookie": SECRETS["Cookie"]},
        )

    emitted = str(raised.value) + "\n" + caplog.text
    for secret in (*SECRETS.values(), "fake-url-SECURITY-TEST"):
        assert secret not in emitted


def test_camera_stream_response_redacts_credentials():
    """Even the opt-in raw-response logger must not expose WebRTC secrets."""
    secrets = {
        "janusToken": "fake-janus-SECURITY-TEST",
        "cameraAuthToken": "fake-camera-SECURITY-TEST",
        "signallingServerToken": "fake-signalling-SECURITY-TEST",
        "proxyUrl": "fake-proxy-SECURITY-TEST",
    }
    original = {
        "data": {
            "attributes": {
                **secrets,
                "iceServers": json.dumps([
                    {
                        "urls": "turn:example.invalid",
                        "username": "fake-turn-user-SECURITY-TEST",
                        "credential": "fake-turn-password-SECURITY-TEST",
                    }
                ]),
            }
        }
    }
    result = _redact_stream_info(original)
    emitted = json.dumps(result)
    for secret in (*secrets.values(), "fake-turn-user-SECURITY-TEST", "fake-turn-password-SECURITY-TEST"):
        assert secret not in emitted
    assert original["data"]["attributes"]["janusToken"] == secrets["janusToken"]


async def test_create_request_logs_no_headers_or_body(caplog):
    """Exercise the actual HTTP wrapper, including MFA cookie injection."""
    bridge = AlarmBridge()
    response = AsyncMock()
    response.cookies = {}
    response.status = 200
    response.request_info.method = "POST"

    @asynccontextmanager
    async def fake_request(*args, **kwargs):
        yield response

    session = MagicMock()
    session.request.side_effect = fake_request
    session.cookie_jar = []
    bridge._websession = session
    bridge._auth_controller.mfa_cookie = SECRETS["twoFactorAuthenticationId"]
    with caplog.at_level(logging.DEBUG):
        async with bridge.create_request(
            "POST", "https://example.invalid/login",
            data={"txtPassword": SECRETS["txtPassword"], "code": SECRETS["otp"]},
            headers={"Cookie": SECRETS["Cookie"]},
        ):
            pass
    for secret in SECRETS.values():
        assert secret not in caplog.text
