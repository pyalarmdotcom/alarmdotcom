"""
Diagnostics support for Alarm.com.

Exposes everything the integration currently knows: config entry data
(redacted), connection/websocket health, and a raw JSON:API dump of every
resource across every controller (locks, sensors, thermostats, cameras,
partitions, etc.) - the same raw data the per-sensor "Debug" button logs
one device at a time, but comprehensive and available as a single
downloadable file via Settings -> Devices & Services -> Alarm.com ->
Download diagnostics (or per-device, from that device's own page).

Sensitive values (credentials, session tokens, camera stream tokens) are
redacted before this data is ever assembled into the returned dict -
diagnostics downloads are meant to be safe to attach to a GitHub issue.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    CONF_ARM_CODE,
    CONF_CAMERA_MFA_CODE,
    CONF_CAMERA_MFA_COOKIE,
    CONF_MFA_TOKEN,
    CONF_OTP,
    DOMAIN,
)

if TYPE_CHECKING:
    from .camera_api import AlarmCameraSession
    from .hub import AlarmHub

_LOGGER = logging.getLogger(__name__)

# Config-entry-level fields, plus every raw JSON:API attribute key known to
# carry a live credential or session token (camera stream tokens in
# particular - see camera_api.py's _redact_stream_info, which redacts the
# same set for the separate, much narrower case of debug logging).
TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ARM_CODE,
    CONF_MFA_TOKEN,
    CONF_OTP,
    CONF_CAMERA_MFA_CODE,
    CONF_CAMERA_MFA_COOKIE,
    "mfa_cookie",
    "proxyUrl",
    "janusToken",
    "signallingServerToken",
    "cameraAuthToken",
    "credential",
    "username",
    "email",
    "ajax_key",
    "publicIp",
    "privateIp",
    "macAddress",
    "networkedDevicePrivateIp",
    "cameraBehindNetworkedDevicePrivateIp",
    "urlForRecordingStream",
}


def _dump_all_resources(hub: AlarmHub) -> dict[str, list[dict[str, Any]]]:
    """
    Return a raw JSON:API dump of every resource across every controller.

    Keyed by controller class name (LockController, SensorController, etc.)
    so the output is grouped by device type without needing HA's own entity
    layer at all - this is the underlying Alarm.com data as the library
    receives it, before any of it gets mapped onto HA entities.

    Note: this deliberately does NOT include real camera data, even though
    a CameraController exists in this list - cameras are fetched through a
    completely separate mechanism (AlarmCameraSession, see
    _camera_diagnostics below), not through fetch_full_state() like every
    other resource type, so CameraController's own .items is always empty in
    practice. Confirmed against a real diagnostics download from a live
    account with real cameras, sensors, locks, and lights: every other
    controller had real counts, only CameraController and a few
    camera-adjacent controllers (GateController, WaterSensorController,
    WaterValveController, ImageSensorImageController) came back with zero
    items - a real, pre-existing architectural gap, not a bug introduced
    here.
    """
    dump: dict[str, list[dict[str, Any]]] = {}
    for controller in hub.api.resource_controllers:
        dump[type(controller).__name__] = [
            resource.api_resource.to_dict() for resource in controller.items
        ]
    return dump


async def _camera_diagnostics(camera_session: AlarmCameraSession | None) -> dict[str, Any]:
    """
    Return camera summary and per-camera stream-connectivity info.

    Sourced from AlarmCameraSession (the same session camera.py itself uses
    to discover and stream cameras) rather than hub.api.cameras, since that
    standard controller is never actually populated - see the note on
    _dump_all_resources. get_stream_info()'s raw response includes live
    session tokens (this is the exact data camera_api.py's own debug
    logging redacts), so it's safe here only because it flows through the
    same async_redact_data(..., TO_REDACT) call every other section does.
    """
    if camera_session is None:
        return {"status": "no_camera_session"}

    try:
        cameras = await camera_session.get_camera_list()
    except Exception as err:
        _LOGGER.debug("Diagnostics: camera list fetch failed: %s", err)
        return {"status": "fetch_failed", "error": str(err)}

    camera_details = []
    for camera in cameras:
        camera_id = camera.get("id")
        detail: dict[str, Any] = {"summary": camera}
        if not isinstance(camera_id, str):
            detail["stream_info"] = {"status": "missing_camera_id"}
            camera_details.append(detail)
            continue
        try:
            detail["stream_info"] = await camera_session.get_stream_info(camera_id)
        except Exception as err:
            _LOGGER.debug(
                "Diagnostics: stream info fetch failed for camera %s: %s", camera_id, err
            )
            detail["stream_info"] = {"status": "fetch_failed", "error": str(err)}
        camera_details.append(detail)

    return {"status": "ok", "cameras": camera_details}


def _connection_health(hub: AlarmHub) -> dict[str, Any]:
    """Return connection/websocket health, independent of any specific device."""
    health: dict[str, Any] = {
        "available": hub.available,
        "active_system": {
            "id": hub.api.active_system.id,
            "name": hub.api.active_system.name,
        }
        if hub.api.active_system
        else None,
    }
    # Raw frames can contain access details and camera storage paths in a
    # query string. Keep only the fields needed to trace event delivery.
    controller = getattr(hub.api, "ws_controller", None)
    if controller is not None:
        events = []
        for frame in controller.last_events:
            try:
                event = json.loads(frame) if isinstance(frame, str) else frame
            except ValueError:
                continue
            if isinstance(event, dict):
                events.append({
                    key: event[key]
                    for key in ("EventDateUtc", "EventType", "DeviceType", "DeviceId")
                    if key in event and isinstance(event[key], (str, int))
                })
        health["last_events"] = events
    return health


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the whole config entry (the full account)."""
    hub: AlarmHub = entry.runtime_data.hub
    camera_session = entry.runtime_data.camera_session

    return async_redact_data(
        {
            "config_entry": {
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            "connection": _connection_health(hub),
            "resources": _dump_all_resources(hub),
            "cameras": await _camera_diagnostics(camera_session),
        },
        TO_REDACT,
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """
    Return diagnostics for a single device's page.

    Same underlying data as the config-entry-wide dump, filtered down to
    just the resource(s) backing this specific HA device - useful when
    someone's reporting an issue with one sensor/lock/camera and doesn't
    need (or want to share) the whole account's data.
    """
    hub: AlarmHub = entry.runtime_data.hub
    camera_session = entry.runtime_data.camera_session

    device_identifiers = {identifier[1] for identifier in device.identifiers if identifier[0] == DOMAIN}

    matching_resources: dict[str, list[dict[str, Any]]] = {}
    for controller in hub.api.resource_controllers:
        matches = [
            resource.api_resource.to_dict()
            for resource in controller.items
            if resource.id in device_identifiers
        ]
        if matches:
            matching_resources[type(controller).__name__] = matches

    all_cameras = await _camera_diagnostics(camera_session)
    matching_cameras = (
        [
            cam
            for cam in all_cameras.get("cameras", [])
            if cam["summary"].get("id") in device_identifiers
        ]
        if all_cameras.get("status") == "ok"
        else []
    )

    return async_redact_data(
        {
            "device": {
                "name": device.name,
                "model": device.model,
                "manufacturer": device.manufacturer,
            },
            "connection": _connection_health(hub),
            "resources": matching_resources,
            "cameras": matching_cameras,
        },
        TO_REDACT,
    )
