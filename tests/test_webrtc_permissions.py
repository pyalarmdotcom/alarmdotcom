"""Keep camera credentials behind per-entity permission checks."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.alarmdotcom.const import DOMAIN
from custom_components.alarmdotcom.webrtc_ws import async_get_webrtc_config


@pytest.mark.parametrize("allowed", [False, True])
async def test_webrtc_credentials_require_camera_permission(hass, allowed):
    """Denied users cannot trigger a token fetch or receive credentials."""
    camera = MagicMock()
    config = {"janusToken": "fake-camera-secret"}
    camera.async_get_webrtc_config = AsyncMock(return_value=config)
    hass.data[DOMAIN + "_camera_entities"] = {"camera.porch": camera}
    connection = MagicMock()
    connection.user.permissions.check_entity.return_value = allowed

    async_get_webrtc_config(hass, connection, {"id": 1, "entity_id": "camera.porch"})
    await hass.async_block_till_done()

    if allowed:
        camera.async_get_webrtc_config.assert_awaited_once()
        connection.send_result.assert_called_once_with(1, config)
    else:
        camera.async_get_webrtc_config.assert_not_awaited()
        connection.send_result.assert_not_called()
        connection.send_error.assert_called_once_with(1, "unauthorized", "Camera access denied")
