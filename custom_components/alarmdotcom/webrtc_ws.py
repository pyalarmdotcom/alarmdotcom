"""
Authenticated, on-demand Alarm.com camera WebRTC credentials.

Credentials must never be exposed as Home Assistant entity attributes.
"""
from __future__ import annotations

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .schema import vol

COMMAND = "alarmdotcom/webrtc_config"


@websocket_api.websocket_command(
    {vol.Required("type"): COMMAND, vol.Required("entity_id"): str}
)
@websocket_api.async_response
async def async_get_webrtc_config(hass: HomeAssistant, connection: ActiveConnection, msg: dict) -> None:
    """Supply ephemeral tokens only to users authorized to read this camera."""
    entity_id = msg["entity_id"]
    if not entity_id.startswith("camera."):
        connection.send_error(msg["id"], "invalid_entity", "Expected a camera entity")
        return

    if not connection.user.permissions.check_entity(entity_id, POLICY_READ):
        connection.send_error(msg["id"], "unauthorized", "Camera access denied")
        return

    camera = hass.data.get(DOMAIN + "_camera_entities", {}).get(entity_id)
    if camera is None:
        connection.send_error(msg["id"], "not_found", "Alarm.com camera not found")
        return

    try:
        config = await camera.async_get_webrtc_config()
    except Exception:
        connection.send_error(msg["id"], "stream_unavailable", "Camera stream unavailable")
        return

    if not config:
        connection.send_error(msg["id"], "stream_unavailable", "Camera stream unavailable")
        return

    # Websocket results are sent directly to the authorized browser, never
    # through the state machine, recorder, or logs.
    connection.send_result(msg["id"], config)


def async_register(hass: HomeAssistant) -> None:
    """Register the command once for all Alarm.com config entries."""
    if hass.data.get(DOMAIN + "_webrtc_registered"):
        return
    websocket_api.async_register_command(hass, async_get_webrtc_config)
    hass.data[DOMAIN + "_webrtc_registered"] = True
