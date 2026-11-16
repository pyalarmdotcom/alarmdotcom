"""Camera transport preference preserves working defaults and the Janus workaround."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.alarmdotcom.camera_api import AlarmCameraSession

E2E_TYPE = "video/videoSources/endToEndWebrtcConnectionInfo"
QUALITY_TYPE = "video/videoSources/webrtcStreamQualityMessage"


async def stream_config(attributes, included, **kwargs):
    """Parse a synthetic API response without making a network request."""
    session = object.__new__(AlarmCameraSession)
    response = MagicMock()
    response.json = AsyncMock(return_value={"data": {"attributes": attributes}, "included": included})
    session.get = AsyncMock(return_value=response)
    return await session.get_stream_info("system-2048", **kwargs)


@pytest.mark.parametrize(("qualities", "expected_id"), [
    ([("Hd", 901), ("Sd", 902)], 901),
    ([("Sd", 902)], 902),
    ([], 2048),
])
async def test_explicit_janus_preference_when_both_transports_are_offered(qualities, expected_id):
    """The server's real stream ID and ICE servers survive transport selection."""
    ice = [{"urls": ["stun:example.test"]}]
    attributes = {"janusGatewayUrl": "wss://example.test/janus", "janusToken": "synthetic", "iceServers": json.dumps(ice)}
    included = [{"type": E2E_TYPE, "attributes": {"cameraAuthToken": "synthetic-e2e"}}]
    included.extend({"type": QUALITY_TYPE, "id": f"system-2048-{quality}", "attributes": {"streamID": stream_id}}
                    for quality, stream_id in qualities)
    config = await stream_config(attributes, included, preferred_transport="janus")
    assert config["streamType"] == "janus"
    assert config["janusStreamId"] == expected_id
    assert config["iceServers"] == ice
    assert "cameraAuthToken" not in config


@pytest.mark.parametrize("attributes", [{}, {"janusGatewayUrl": "wss://example.test/janus"}, {"janusToken": "synthetic"}])
async def test_end_to_end_remains_available_without_complete_janus_credentials(attributes):
    """Never select a proxy transport with missing credentials."""
    config = await stream_config(attributes, [{"type": E2E_TYPE, "attributes": {"cameraAuthToken": "synthetic-e2e"}}], preferred_transport="janus")
    assert config["streamType"] == "endToEnd"
    assert config["cameraAuthToken"] == "synthetic-e2e"


async def test_no_transport_returns_no_configuration():
    """An offline or unsupported camera must not get fabricated credentials."""
    assert await stream_config({}, []) is None


async def test_default_transport_preserves_pre_regression_end_to_end():
    """Existing kiosk dashboards must not silently switch to Janus (#177)."""
    config = await stream_config(
        {"janusGatewayUrl": "wss://example.test/janus", "janusToken": "synthetic"},
        [{"type": E2E_TYPE, "attributes": {"cameraAuthToken": "synthetic-e2e"}}],
    )
    assert config["streamType"] == "endToEnd"


async def test_default_falls_back_to_janus_for_janus_only_cameras():
    """Doorbells that only advertise Janus remain supported."""
    config = await stream_config(
        {"janusGatewayUrl": "wss://example.test/janus", "janusToken": "synthetic"}, [],
    )
    assert config["streamType"] == "janus"
