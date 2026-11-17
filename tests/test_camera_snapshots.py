"""Snapshot metadata stays authenticated; signed images use a cookie-free client."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.alarmdotcom.camera import AlarmDotComCamera
from custom_components.alarmdotcom.camera_api import AlarmCameraSession

SIGNED_URL = "https://video.example.test/image.jpg?signature=synthetic-secret"


def make_camera():
    """Construct a camera without a live Alarm.com session."""
    session = MagicMock()
    session.get_snapshot_url = AsyncMock(return_value=SIGNED_URL)
    return AlarmDotComCamera(session, {"id": "cam-1"}, "entry", timedelta(minutes=30))


@pytest.mark.parametrize(("attributes", "expected"), [
    ({"url": SIGNED_URL}, SIGNED_URL),
    ({"url": SIGNED_URL, "error": "unavailable"}, None),
    ({"url": 123}, None),
    ({}, None),
])
async def test_snapshot_url_uses_api_metadata(attributes, expected):
    """Read the documented URL field without confusing it with image bytes."""
    session = object.__new__(AlarmCameraSession)
    response = MagicMock()
    response.json = AsyncMock(return_value={"data": {"attributes": attributes}})
    session.get = AsyncMock(return_value=response)
    assert await session.get_snapshot_url("cam-1") == expected
    session.get.assert_awaited_once_with("https://www.alarm.com/web/api/video/snapshots/cam-1")
    response.release.assert_called_once()


@pytest.mark.parametrize(("content_type", "status", "chunks", "expected"), [
    ("image/jpeg", 200, [b"image-", b"bytes"], b"image-bytes"),
    ("application/json", 200, [b"error"], None),
    ("text/html", 200, [b"login page"], None),
    ("image/jpeg", 302, [], None),
    ("image/jpeg", 200, [], None),
    ("image/jpeg", 200, [b"x" * (10 * 1024 * 1024 + 1)], None),
])
async def test_snapshot_download_is_isolated_and_validated(content_type, status, chunks, expected):
    """Never attach Alarm.com cookies or headers to the separate video host."""
    camera = make_camera()
    response = MagicMock(status=status, content_type=content_type)

    async def stream(_size):
        for chunk in chunks:
            yield chunk

    response.content.iter_chunked = stream
    download = MagicMock()
    download.__aenter__ = AsyncMock(return_value=response)
    download.__aexit__ = AsyncMock(return_value=False)
    client = MagicMock()
    client.get.return_value = download
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)
    with patch("custom_components.alarmdotcom.camera.aiohttp.ClientSession", return_value=context) as constructor:
        assert await camera.async_camera_image() == expected
    assert isinstance(constructor.call_args.kwargs["cookie_jar"], aiohttp.DummyCookieJar)
    assert constructor.call_args.kwargs["timeout"].total == 15
    assert str(client.get.call_args.args[0]) == SIGNED_URL
    assert client.get.call_args.kwargs == {"allow_redirects": False}
    camera._session.get_snapshot_url.assert_awaited_once_with("cam-1")
    assert camera.extra_state_attributes == {}


@pytest.mark.parametrize("url", [None, "http://video.example.test/image", "https://user:secret@video.example.test/image"])
async def test_missing_or_unsafe_snapshot_url_does_not_download(url):
    """Only a nonempty HTTPS URL without embedded credentials is usable."""
    camera = make_camera()
    camera._session.get_snapshot_url.return_value = url
    with patch("custom_components.alarmdotcom.camera.aiohttp.ClientSession") as constructor:
        assert await camera.async_camera_image() is None
    constructor.assert_not_called()


async def test_snapshot_failure_does_not_log_signed_url(caplog):
    """Transport exceptions may include the signed URL; suppress their text."""
    camera = make_camera()
    camera._session.get_snapshot_url.side_effect = RuntimeError(SIGNED_URL)
    with caplog.at_level("DEBUG", logger="custom_components.alarmdotcom.camera"):
        assert await camera.async_camera_image() is None
    assert "RuntimeError" in caplog.text
    assert "synthetic-secret" not in caplog.text
