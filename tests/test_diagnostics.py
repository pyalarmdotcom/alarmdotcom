"""
Tests for diagnostics.py.

The redaction tests matter most here: diagnostics downloads are meant to
be safe to attach to a GitHub issue, so a regression that stops sensitive
fields from being redacted is a real, if quiet, security-relevant bug.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alarmdotcom import AlarmEntryData
from custom_components.alarmdotcom.const import DOMAIN
from custom_components.alarmdotcom.diagnostics import (
    _connection_health,
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)

VALID_DATA = {"username": "test@example.com", "password": "hunter2"}


def _make_resource(resource_id: str, raw_dict: dict) -> MagicMock:
    """Build a mock resource whose api_resource.to_dict() returns the given raw dict."""
    resource = MagicMock()
    resource.id = resource_id
    resource.api_resource.to_dict.return_value = raw_dict
    return resource


def _make_controller(class_name: str, resources: list) -> MagicMock:
    """Build a mock controller with the given class name and resource list."""
    controller = MagicMock()
    controller.__class__.__name__ = class_name
    controller.items = resources
    return controller


@pytest.fixture
def mock_hub_with_camera_resource():
    """Build a mock hub with one controller containing one resource with live camera tokens."""
    hub = MagicMock()
    hub.available = True
    hub.api.active_system.id = "12345"
    hub.api.active_system.name = "Test System"

    camera_resource = _make_resource(
        "cam-1",
        {
            "id": "cam-1",
            "type": "video/camera",
            "attributes": {
                "description": "Front Door",
                "proxyUrl": "SECRET_PROXY_URL",
                "janusToken": "SECRET_JANUS_TOKEN",
            },
        },
    )
    hub.api.resource_controllers = [_make_controller("CameraController", [camera_resource])]
    return hub


def test_recent_events_exclude_raw_camera_metadata(mock_hub_with_camera_resource) -> None:
    """Raw websocket JSON must not bypass the normal redaction pass."""
    hub = mock_hub_with_camera_resource
    hub.api.ws_controller.last_events = [
        '{"EventType":210,"DeviceId":20,"QstringForExtraData":"path=private-storage-sentinel"}',
        "not a JSON event",
    ]

    assert _connection_health(hub)["last_events"] == [{"EventType": 210, "DeviceId": 20}]


async def test_config_entry_diagnostics_redacts_credentials(hass, mock_hub_with_camera_resource) -> None:
    """Username/password in config entry data must never appear unredacted."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_DATA)
    entry.add_to_hass(hass)
    entry.runtime_data = AlarmEntryData(
        hub=mock_hub_with_camera_resource,
        auto_off_manager=MagicMock(),
        camera_session=None,
        activity_feed_tracker=MagicMock(),
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["config_entry"]["data"]["username"] == "**REDACTED**"
    assert result["config_entry"]["data"]["password"] == "**REDACTED**"


async def test_config_entry_diagnostics_redacts_camera_tokens(hass, mock_hub_with_camera_resource) -> None:
    """
    Live camera stream tokens must never appear unredacted in the resource dump.

    This is the core regression test: a diagnostics download containing
    live janusToken/proxyUrl values would let anyone who sees the file
    access that camera's stream during the token's validity window.
    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_DATA)
    entry.add_to_hass(hass)
    entry.runtime_data = AlarmEntryData(
        hub=mock_hub_with_camera_resource,
        auto_off_manager=MagicMock(),
        camera_session=None,
        activity_feed_tracker=MagicMock(),
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    camera_dump = result["resources"]["CameraController"][0]
    assert camera_dump["attributes"]["proxyUrl"] == "**REDACTED**"
    assert camera_dump["attributes"]["janusToken"] == "**REDACTED**"
    # Confirm non-sensitive fields survive redaction untouched - this isn't
    # a blanket wipe, only the specific known-sensitive keys are affected.
    assert camera_dump["attributes"]["description"] == "Front Door"
    assert camera_dump["id"] == "cam-1"


async def test_config_entry_diagnostics_includes_connection_health(hass, mock_hub_with_camera_resource) -> None:
    """Connection health (available, active system) is present and not redacted."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_DATA)
    entry.add_to_hass(hass)
    entry.runtime_data = AlarmEntryData(
        hub=mock_hub_with_camera_resource,
        auto_off_manager=MagicMock(),
        camera_session=None,
        activity_feed_tracker=MagicMock(),
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["connection"]["available"] is True
    assert result["connection"]["active_system"]["id"] == "12345"


async def test_device_diagnostics_filters_to_matching_device(hass, mock_hub_with_camera_resource) -> None:
    """Device-level diagnostics only include resources matching that device's identifiers."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_DATA)
    entry.add_to_hass(hass)
    entry.runtime_data = AlarmEntryData(
        hub=mock_hub_with_camera_resource,
        auto_off_manager=MagicMock(),
        camera_session=None,
        activity_feed_tracker=MagicMock(),
    )

    device = MagicMock()
    device.name = "Front Door Camera"
    device.model = "Camera"
    device.manufacturer = "Alarm.com"
    device.identifiers = {(DOMAIN, "cam-1")}

    result = await async_get_device_diagnostics(hass, entry, device)

    assert "CameraController" in result["resources"]
    assert result["resources"]["CameraController"][0]["attributes"]["proxyUrl"] == "**REDACTED**"


async def test_device_diagnostics_excludes_other_devices(hass, mock_hub_with_camera_resource) -> None:
    """A device page should not leak other devices' data."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_DATA)
    entry.add_to_hass(hass)
    entry.runtime_data = AlarmEntryData(
        hub=mock_hub_with_camera_resource,
        auto_off_manager=MagicMock(),
        camera_session=None,
        activity_feed_tracker=MagicMock(),
    )

    device = MagicMock()
    device.name = "Some Other Device"
    device.model = "Lock"
    device.manufacturer = "Alarm.com"
    device.identifiers = {(DOMAIN, "lock-99")}

    result = await async_get_device_diagnostics(hass, entry, device)

    assert result["resources"] == {}


@pytest.fixture
def mock_camera_session():
    """
    Build a mock AlarmCameraSession with one camera whose stream_info carries live tokens.

    Cameras are fetched through this separate session, not through the
    standard resource_controllers list - see the note in diagnostics.py's
    _dump_all_resources for why. Found by inspecting a real diagnostics
    download from a live account: CameraController showed 0 items despite
    real cameras existing, because nothing populates it via the normal
    fetch_full_state() path.
    """
    session = MagicMock()
    session.get_camera_list = AsyncMock(
        return_value=[{"id": "cam-1", "description": "Front Door"}]
    )
    session.get_stream_info = AsyncMock(
        return_value={
            "data": {
                "attributes": {
                    "proxyUrl": "SECRET_PROXY_URL",
                    "janusToken": "SECRET_JANUS_TOKEN",
                }
            }
        }
    )
    return session


async def test_config_entry_diagnostics_includes_and_redacts_camera_session_data(
    hass, mock_hub_with_camera_resource, mock_camera_session
) -> None:
    """
    Camera data from the real camera session is included and redacted.

    This is the actual regression test for the gap found via a real
    diagnostics download: cameras must show up at all (not just an empty
    CameraController), and get_stream_info's live tokens must be redacted
    the same as everywhere else - this data flows through the same
    async_redact_data(..., TO_REDACT) call, but it's worth confirming
    directly rather than assuming.
    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_DATA)
    entry.add_to_hass(hass)
    entry.runtime_data = AlarmEntryData(
        hub=mock_hub_with_camera_resource,
        auto_off_manager=MagicMock(),
        camera_session=mock_camera_session,
        activity_feed_tracker=MagicMock(),
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["cameras"]["status"] == "ok"
    camera = result["cameras"]["cameras"][0]
    assert camera["summary"]["id"] == "cam-1"
    assert camera["stream_info"]["data"]["attributes"]["proxyUrl"] == "**REDACTED**"
    assert camera["stream_info"]["data"]["attributes"]["janusToken"] == "**REDACTED**"


async def test_config_entry_diagnostics_camera_session_none_is_reported_cleanly(
    hass, mock_hub_with_camera_resource
) -> None:
    """No camera session (e.g. camera login never succeeded) is reported, not a crash."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_DATA)
    entry.add_to_hass(hass)
    entry.runtime_data = AlarmEntryData(
        hub=mock_hub_with_camera_resource,
        auto_off_manager=MagicMock(),
        camera_session=None,
        activity_feed_tracker=MagicMock(),
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["cameras"]["status"] == "no_camera_session"


async def test_config_entry_diagnostics_camera_fetch_failure_does_not_break_whole_dump(
    hass, mock_hub_with_camera_resource
) -> None:
    """A camera-list fetch failure is reported, not allowed to crash the whole diagnostics call."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_DATA)
    entry.add_to_hass(hass)
    failing_session = MagicMock()
    failing_session.get_camera_list = AsyncMock(side_effect=ConnectionError("boom"))
    entry.runtime_data = AlarmEntryData(
        hub=mock_hub_with_camera_resource,
        auto_off_manager=MagicMock(),
        camera_session=failing_session,
        activity_feed_tracker=MagicMock(),
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["cameras"]["status"] == "fetch_failed"
    # The rest of the diagnostics dump should still be present and correct.
    assert result["connection"]["available"] is True


async def test_device_diagnostics_includes_matching_camera_only(
    hass, mock_hub_with_camera_resource, mock_camera_session
) -> None:
    """A camera's own device page includes its camera session data, filtered to just that camera."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=VALID_DATA)
    entry.add_to_hass(hass)
    entry.runtime_data = AlarmEntryData(
        hub=mock_hub_with_camera_resource,
        auto_off_manager=MagicMock(),
        camera_session=mock_camera_session,
        activity_feed_tracker=MagicMock(),
    )

    device = MagicMock()
    device.name = "Front Door Camera"
    device.model = "Camera"
    device.manufacturer = "Alarm.com"
    device.identifiers = {(DOMAIN, "cam-1")}

    result = await async_get_device_diagnostics(hass, entry, device)

    assert len(result["cameras"]) == 1
    assert result["cameras"][0]["stream_info"]["data"]["attributes"]["proxyUrl"] == "**REDACTED**"
