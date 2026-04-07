"""Alarm.com Camera API for fetching camera list and WebRTC stream info."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

URL_BASE = "https://www.alarm.com/"
API_URL_BASE = URL_BASE + "web/api/"
MFA_COOKIE_KEY = "twoFactorAuthenticationId"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)
REFERER = "https://www.alarm.com/web/system/home"

VIEWSTATE_FIELD = "__VIEWSTATE"
VIEWSTATEGENERATOR_FIELD = "__VIEWSTATEGENERATOR"
EVENTVALIDATION_FIELD = "__EVENTVALIDATION"
PREVIOUSPAGE_FIELD = "__PREVIOUSPAGE"

ACCEPT_HTML = {"Accept": "text/html,application/xhtml+xml,application/xml"}
ACCEPT_JSON = {"Accept": "application/json", "charset": "utf-8"}
ACCEPT_JSONAPI = {"Accept": "application/vnd.api+json", "charset": "utf-8"}
CONTENT_FORM = {"Content-Type": "application/x-www-form-urlencoded", "charset": "utf-8"}


def _build_headers(
    accept: dict[str, str] | None = None,
    ajax_key: str | None = None,
) -> dict[str, str]:
    """Build request headers."""

    headers: dict[str, str] = {
        "User-Agent": USER_AGENT,
        "Referer": REFERER,
        "Connection": "keep-alive",
    }
    if accept:
        headers.update(accept)
    if ajax_key:
        headers["Ajaxrequestuniquekey"] = ajax_key
    return headers


class AlarmCameraSession:
    """Manages an authenticated Alarm.com session for camera operations."""

    def __init__(
        self,
        username: str,
        password: str,
        mfa_cookie: str | None = None,
    ) -> None:
        """Initialize."""

        self.username = username
        self.password = password
        self.ajax_key: str | None = None
        self.mfa_cookie: str | None = mfa_cookie
        self.cookie_jar = aiohttp.CookieJar(unsafe=True)
        self.session: aiohttp.ClientSession | None = None
        self._logged_in = False

    def _extra_cookies(self) -> dict[str, str]:
        """Return MFA cookie if available."""

        cookies: dict[str, str] = {}
        if self.mfa_cookie:
            cookies[MFA_COOKIE_KEY] = self.mfa_cookie
        return cookies

    def _extract_cookies(self, resp: aiohttp.ClientResponse) -> None:
        """Extract session cookies from response."""

        if afg := resp.cookies.get("afg"):
            self.ajax_key = afg.value
        if (mfa := resp.cookies.get(MFA_COOKIE_KEY)) and mfa.value != self.mfa_cookie:
            self.mfa_cookie = mfa.value

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure an aiohttp session exists."""

        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(cookie_jar=self.cookie_jar)
        return self.session

    async def _get(
        self,
        url: str,
        *,
        accept: dict[str, str] | None = None,
        use_ajax: bool = True,
    ) -> aiohttp.ClientResponse:
        """Perform an authenticated GET request."""

        session = await self._ensure_session()
        resp = await session.get(
            url,
            headers=_build_headers(accept or ACCEPT_JSONAPI, self.ajax_key if use_ajax else None),
            cookies=self._extra_cookies(),
            allow_redirects=True,
        )
        self._extract_cookies(resp)
        resp.raise_for_status()
        return resp

    async def _post(
        self,
        url: str,
        *,
        accept: dict[str, str] | None = None,
        use_ajax: bool = True,
        data: dict[str, Any] | None = None,
    ) -> aiohttp.ClientResponse:
        """Perform an authenticated POST request."""

        session = await self._ensure_session()
        kwargs: dict[str, Any] = {
            "headers": _build_headers(accept or ACCEPT_JSONAPI, self.ajax_key if use_ajax else None),
            "cookies": self._extra_cookies(),
            "allow_redirects": True,
        }
        if data is not None:
            kwargs["data"] = data
        resp = await session.post(url, **kwargs)
        self._extract_cookies(resp)
        resp.raise_for_status()
        return resp

    async def login(self) -> bool:
        """Perform login to Alarm.com web interface."""

        log.debug("Camera API: Loading login page...")
        resp = await self._get(f"{URL_BASE}login", accept=ACCEPT_HTML, use_ajax=False)
        html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")

        fields: dict[str, str] = {}
        for field_id in (VIEWSTATE_FIELD, VIEWSTATEGENERATOR_FIELD, EVENTVALIDATION_FIELD, PREVIOUSPAGE_FIELD):
            element = soup.select_one(f"#{field_id}")
            if element is None:
                log.error("Camera API: Could not find #%s in login page.", field_id)
                return False
            fields[field_id] = str(element.attrs.get("value", ""))

        log.debug("Camera API: Submitting credentials...")
        resp = await self._post(
            f"{URL_BASE}web/Default.aspx",
            accept=CONTENT_FORM,
            use_ajax=True,
            data={
                "ctl00$ContentPlaceHolder1$loginform$txtUserName": self.username,
                "txtPassword": self.password,
                VIEWSTATE_FIELD: fields[VIEWSTATE_FIELD],
                VIEWSTATEGENERATOR_FIELD: fields[VIEWSTATEGENERATOR_FIELD],
                EVENTVALIDATION_FIELD: fields[EVENTVALIDATION_FIELD],
                PREVIOUSPAGE_FIELD: fields[PREVIOUSPAGE_FIELD],
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "__VIEWSTATEENCRYPTED": "",
                "IsFromNewSite": "1",
            },
        )

        url_str = str(resp.url)
        if "m=login_fail" in url_str:
            log.error("Camera API: Login failed - bad credentials.")
            return False
        if "m=LockedOut" in url_str:
            log.error("Camera API: Account locked out.")
            return False

        self._logged_in = True
        log.info("Camera API: Login successful.")
        return True

    async def get_camera_list(self) -> list[dict[str, Any]]:
        """Fetch list of cameras from Alarm.com."""

        if not self._logged_in and not await self.login():
            return []

        try:
            resp = await self._get(f"{API_URL_BASE}video/devices/cameras")
            body = await resp.json()
        except aiohttp.ClientResponseError:
            log.warning("Camera API: Failed to fetch camera list. Retrying with fresh login...")
            self._logged_in = False
            if not await self.login():
                return []
            resp = await self._get(f"{API_URL_BASE}video/devices/cameras")
            body = await resp.json()

        cameras: list[dict[str, Any]] = []
        data = body.get("data", [])
        if isinstance(data, dict):
            data = [data]
        for cam in data:
            attrs = cam.get("attributes", {})
            summary: dict[str, Any] = {"id": cam.get("id")}
            summary.update(attrs)
            cameras.append(summary)
        return cameras

    async def get_stream_info(self, camera_id: str) -> dict[str, Any] | None:
        """Fetch WebRTC stream configuration for a camera."""

        if not self._logged_in and not await self.login():
            return None

        try:
            resp = await self._get(
                f"{API_URL_BASE}video/videoSources/liveVideoHighestResSources/{camera_id}",
            )
            body = await resp.json()
        except aiohttp.ClientResponseError:
            log.warning("Camera API: Failed to fetch stream info. Retrying with fresh login...")
            self._logged_in = False
            if not await self.login():
                return None
            try:
                resp = await self._get(
                    f"{API_URL_BASE}video/videoSources/liveVideoHighestResSources/{camera_id}",
                )
                body = await resp.json()
            except aiohttp.ClientResponseError:
                log.error("Camera API: Failed to fetch stream info for camera %s.", camera_id)
                return None

        top_attrs = body.get("data", {}).get("attributes", {})
        ice_servers_str = top_attrs.get("iceServers")
        ice_servers = json.loads(ice_servers_str) if ice_servers_str else []

        included = body.get("included", [])
        for inc in included:
            if inc.get("type") == "video/videoSources/endToEndWebrtcConnectionInfo":
                config: dict[str, Any] = inc.get("attributes", {})
                config["iceServers"] = ice_servers
                return config

        return None

    async def close(self) -> None:
        """Close the session."""

        if self.session and not self.session.closed:
            await self.session.close()
