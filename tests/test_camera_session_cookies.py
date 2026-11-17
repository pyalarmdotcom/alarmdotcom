"""Camera requests follow shared-session anti-forgery cookie rotation (#156)."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from yarl import URL

from custom_components.alarmdotcom.camera_api import API_URL_BASE, AlarmCameraSession


@pytest.mark.parametrize("method", ["get", "post"])
async def test_camera_uses_rotated_shared_cookie_before_request(method):
    """A bridge refresh must not make the next camera call send an obsolete header."""
    jar = aiohttp.CookieJar()
    url = API_URL_BASE + "video/devices/cameras"
    jar.update_cookies({"afg": "synthetic-original"}, URL(url))
    http = MagicMock(cookie_jar=jar)
    response = MagicMock(cookies={})
    http.get = AsyncMock(return_value=response)
    http.post = AsyncMock(return_value=response)
    session = AlarmCameraSession("user", session=http, ajax_key="synthetic-original", _owns_session=False)
    # A bridge request renews cookies while this camera is idle.
    jar.update_cookies({"afg": "synthetic-rotated"}, URL(url))
    if method == "get":
        await session.get(url)
    else:
        await session._post(url)
    request = getattr(http, method)
    assert request.call_args.kwargs["headers"]["Ajaxrequestuniquekey"] == "synthetic-rotated"
    assert session.ajax_key == "synthetic-rotated"


async def test_missing_cookie_keeps_key_and_other_domains_are_ignored():
    """Providers without an afg cookie retain the existing supported behavior."""
    jar = aiohttp.CookieJar()
    jar.update_cookies({"afg": "unrelated"}, URL("https://other.example.test/"))
    http = MagicMock(cookie_jar=jar)
    session = AlarmCameraSession("user", session=http, ajax_key="synthetic-existing", _owns_session=False)
    session._sync_ajax_key(API_URL_BASE)
    assert session.ajax_key == "synthetic-existing"
