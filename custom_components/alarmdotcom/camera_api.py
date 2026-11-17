"""Alarm.com camera API, WebRTC session manager."""

from __future__ import annotations

import asyncio
import json
import logging
from enum import Enum
from typing import TYPE_CHECKING

import aiohttp
from bs4 import BeautifulSoup
from yarl import URL

if TYPE_CHECKING:
    from _pyalarmdotcomajax import AlarmBridge

URL_BASE = "https://www.alarm.com/"
API_URL_BASE = URL_BASE + "web/api/"

MFA_COOKIE_KEY = "twoFactorAuthenticationId"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
REFERER = "https://www.alarm.com/web/system/home"

VIEWSTATE_FIELD = "__VIEWSTATE"
VIEWSTATEGENERATOR_FIELD = "__VIEWSTATEGENERATOR"
EVENTVALIDATION_FIELD = "__EVENTVALIDATION"
PREVIOUSPAGE_FIELD = "__PREVIOUSPAGE"

TWO_FACTOR_PATH = "engines/twoFactorAuthentication/twoFactorAuthentications"

_LOGGER = logging.getLogger(__name__)
# Raw camera stream responses contain live, unexpired session credentials
# (janusToken, cameraAuthToken, signallingServerToken, TURN credentials) and
# are extremely verbose (fire on every WebRTC token refresh, roughly every
# 20-30 seconds per camera). Logged through a separate child logger so they
# don't show up just because someone enabled debug logging for
# custom_components.alarmdotcom generally - see get_stream_info() below.
_RAW_RESPONSE_LOGGER = logging.getLogger(f"{__name__}.raw_responses")
# Default this child logger to WARNING so it does NOT inherit DEBUG just
# because someone enabled Home Assistant's standard "Enable debug logging"
# toggle for the integration (which sets custom_components.alarmdotcom to
# DEBUG, and child loggers inherit their effective level from the nearest
# ancestor with an explicit level). Only set the default if nothing more
# specific has already been configured for this exact logger name (e.g. via
# configuration.yaml's `logger:` integration) - checking .level (not
# .getEffectiveLevel()) distinguishes "explicitly set on this logger" from
# "inherited," so this never overwrites a user's own explicit choice
# regardless of which runs first at startup.
if _RAW_RESPONSE_LOGGER.level == logging.NOTSET:
    _RAW_RESPONSE_LOGGER.setLevel(logging.WARNING)

_REDACTED = "[REDACTED]"
_SENSITIVE_ATTRIBUTE_KEYS = {
    "proxyUrl",
    "janusToken",
    "signallingServerToken",
    "cameraAuthToken",
}


def _redact_stream_info(body: dict) -> dict:
    """
    Return a deep copy of a get_stream_info response with credentials masked.

    Safe to log at normal debug level. Masks the known sensitive attribute
    keys plus iceServers TURN credentials/usernames (which are themselves
    time-limited but still live access credentials while valid).
    """

    redacted: dict = json.loads(json.dumps(body))  # cheap deep copy via round-trip

    def _redact_attributes(attributes: dict) -> None:
        for key in _SENSITIVE_ATTRIBUTE_KEYS:
            if key in attributes:
                attributes[key] = _REDACTED
        ice_servers_s = attributes.get("iceServers")
        if ice_servers_s:
            try:
                ice_servers = json.loads(ice_servers_s)
                for server in ice_servers:
                    if "credential" in server:
                        server["credential"] = _REDACTED
                    if "username" in server:
                        server["username"] = _REDACTED
                attributes["iceServers"] = json.dumps(ice_servers)
            except Exception:
                attributes["iceServers"] = _REDACTED

    data_attrs = redacted.get("data", {}).get("attributes")
    if isinstance(data_attrs, dict):
        _redact_attributes(data_attrs)

    for item in redacted.get("included", []):
        item_attrs = item.get("attributes")
        if isinstance(item_attrs, dict):
            _redact_attributes(item_attrs)

    return redacted



class OtpType(Enum):
    """MFA types supported by Alarm.com."""

    disabled = 0
    app = 1
    sms = 2
    email = 4


class AuthResult(Enum):
    """Result of an authentication attempt."""

    SUCCESS = "success"
    MFA_REQUIRED = "mfa_required"
    ERROR = "error"


ACCEPT_HTML = {"Accept": "text/html,application/xhtml+xml,application/xml"}
ACCEPT_JSON = {"Accept": "application/json", "charset": "utf-8"}
ACCEPT_JSONAPI = {"Accept": "application/vnd.api+json", "charset": "utf-8"}
CONTENT_FORM = {"Content-Type": "application/x-www-form-urlencoded", "charset": "utf-8"}


def _build_headers(
    accept: dict[str, str] | None = None,
    ajax_key: str | None = None,
) -> dict[str, str]:
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
    """Manages an authenticated Alarm.com HTTP session for camera/WebRTC access."""

    def __init__(
        self,
        username: str,
        password: str | None = None,
        cookie_jar: aiohttp.CookieJar | None = None,
        session: aiohttp.ClientSession | None = None,
        ajax_key: str | None = None,
        mfa_cookie: str | None = None,
        identity_id: str | None = None,
        *,
        _owns_session: bool = True,
    ) -> None:
        self.username = username
        self.password = password
        self.ajax_key = ajax_key
        self.mfa_cookie = mfa_cookie
        self.identity_id = identity_id
        self._owns_session = _owns_session

        self.cookie_jar = cookie_jar or aiohttp.CookieJar(unsafe=True)
        self.session = session or aiohttp.ClientSession(cookie_jar=self.cookie_jar)

        # Guards concurrent re-login. All camera entities on a config entry share one
        # AlarmCameraSession, and each schedules its own independent 30-minute token
        # refresh timer starting at entity setup, so their timers fire in near-lockstep.
        # When the shared session's auth ages out, every camera hits 401/403 at once and,
        # without this, each independently calls login() on the same session - producing
        # N simultaneous real logins against Alarm.com every refresh interval. This mirrors
        # the AlarmBridge single-flight fix in _pyalarmdotcomajax/__init__.py.
        self._login_lock = asyncio.Lock()
        self._login_generation = 0
        self._replacement_session: AlarmCameraSession | None = None

    @property
    def session_generation(self) -> int:
        """
        Return the current login generation.

        Callers should snapshot this before a request that might fail with 401/403,
        then pass the snapshot to ensure_login() on failure. This lets a caller that
        queues on the login lock discover the session was already repaired by another
        concurrent caller while it waited, and skip a redundant login.
        """
        return self._login_generation

    async def ensure_login(self, prior_generation: int) -> None:
        """
        Repair the session by logging in, unless another caller already has.

        See session_generation for the expected snapshot-then-repair usage pattern.
        """
        async with self._login_lock:
            if prior_generation == self._login_generation:
                await self.login()
                self._login_generation += 1
            else:
                _LOGGER.debug(
                    "Session already repaired by another caller; skipping login."
                )

    async def repair_shared_session(self, prior_generation: int) -> AlarmCameraSession:
        """
        Replace a stale, externally-owned (owns_session=False) session with an independent one.

        All camera entities on a config entry start out referencing the same
        AlarmBridge-extracted session (see from_alarm_bridge). When that session goes
        stale, without coordination each camera independently creates and logs into
        its own separate replacement session on the same ~30-minute refresh cycle -
        producing one real Alarm.com login per camera, all at once, repeatedly. Call
        this instead of constructing a replacement directly: the first caller performs
        the swap-and-login and caches the result on this (the original, now-stale)
        session; concurrent or subsequently-failing callers on the same generation
        reuse the cached replacement instead of creating their own.
        """
        async with self._login_lock:
            if prior_generation == self._login_generation:
                _LOGGER.info(
                    "Shared camera session became stale, creating independent session."
                )
                replacement = AlarmCameraSession(
                    username=self.username,
                    password=self.password,
                    mfa_cookie=self.mfa_cookie,
                )
                await replacement.login()
                self._replacement_session = replacement
                self._login_generation += 1
            else:
                _LOGGER.debug(
                    "Independent session already created by another camera; reusing it."
                )
        if self._replacement_session is None:
            raise RuntimeError(
                "repair_shared_session: no replacement session available after repair"
            )
        return self._replacement_session

    @property
    def owns_session(self) -> bool:
        """
        Return whether this instance created its own aiohttp session.

        True unless a session was passed in externally (e.g. reusing the
        vendored library's own session) - determines whether close() should
        actually close the underlying session, and whether a fresh login is
        needed versus reusing credentials already established elsewhere.
        """
        return self._owns_session

    @classmethod
    def from_alarm_bridge(
        cls,
        bridge: AlarmBridge,
        username: str,
        password: str,
        mfa_cookie: str | None = None,
    ) -> AlarmCameraSession:
        """Create a camera session that reuses the pyalarmdotcomajax HTTP session."""

        session_candidates = [
            lambda b: getattr(b, "_websession", None),
            lambda b: getattr(b, "_session", None),
            lambda b: getattr(b, "_http_session", None),
            lambda b: getattr(getattr(b, "_auth_controller", None), "_session", None),
            lambda b: getattr(getattr(b, "_auth_controller", None), "_http_session", None),
            lambda b: getattr(b, "_client", None),
        ]

        ajax_key_candidates = [
            lambda b: getattr(b, "ajax_key", None),
            lambda b: getattr(b, "_ajax_key", None),
            lambda b: getattr(b, "_afg", None),
            lambda b: getattr(getattr(b, "_auth_controller", None), "_ajax_key", None),
            lambda b: getattr(getattr(b, "_auth_controller", None), "_afg", None),
        ]

        mfa_candidates = [
            lambda b: getattr(getattr(b, "_auth_controller", None), "mfa_cookie", None),
        ]

        extracted_session: aiohttp.ClientSession | None = None
        extracted_ajax_key: str | None = None
        extracted_mfa_cookie: str | None = None

        for fn in session_candidates:
            try:
                val = fn(bridge)
                if isinstance(val, aiohttp.ClientSession) and not val.closed:
                    extracted_session = val
                    _LOGGER.debug(
                        "Camera session: reusing pyalarmdotcomajax internal session."
                    )
                    break
            except Exception as err:
                _LOGGER.debug("Camera session: session candidate %s failed: %s", fn, err)
                continue

        for fn in ajax_key_candidates:
            try:
                val = fn(bridge)
                if isinstance(val, str) and val:
                    extracted_ajax_key = val
                    _LOGGER.debug("Camera session: reusing pyalarmdotcomajax ajax key.")
                    break
            except Exception as err:
                _LOGGER.debug("Camera session: ajax key candidate %s failed: %s", fn, err)
                continue

        for fn in mfa_candidates:
            try:
                val = fn(bridge)
                if isinstance(val, str) and val:
                    extracted_mfa_cookie = val
                    break
            except Exception as err:
                _LOGGER.debug("Camera session: MFA cookie candidate %s failed: %s", fn, err)
                continue

        if extracted_session is not None:
            return cls(
                username=username,
                password=password,
                session=extracted_session,
                ajax_key=extracted_ajax_key,
                mfa_cookie=extracted_mfa_cookie or mfa_cookie,
                _owns_session=False,
            )

        _LOGGER.warning(
            "Camera session: could not extract session from pyalarmdotcomajax "
            "(library internals may have changed). Falling back to independent login."
        )
        return cls(username=username, password=password, mfa_cookie=mfa_cookie)

    @property
    def session_data(self) -> dict:
        """Return session state dict for persistence."""
        return {
            "ajax_key": self.ajax_key,
            "mfa_cookie": self.mfa_cookie,
            "identity_id": self.identity_id,
        }

    def _extra_cookies(self) -> dict[str, str]:
        """Inject MFA cookie explicitly when needed."""
        return {MFA_COOKIE_KEY: self.mfa_cookie} if self.mfa_cookie else {}

    def _sync_ajax_key(self, url: str) -> None:
        """Use the current anti-forgery cookie before sending an API request."""
        # The main bridge can renew our shared session between camera requests.
        # Its cookie jar changes, but the key copied at camera setup does not.
        # Sending the old header can cause a 403 and an unnecessary camera login.
        if (afg := self.session.cookie_jar.filter_cookies(URL(url)).get("afg")) and afg.value:
            self.ajax_key = afg.value

    def _extract_cookies(self, resp: aiohttp.ClientResponse) -> None:
        afg = resp.cookies.get("afg")
        if afg:
            self.ajax_key = afg.value

        mfa = resp.cookies.get(MFA_COOKIE_KEY)
        if mfa and mfa.value != self.mfa_cookie:
            self.mfa_cookie = mfa.value

    async def get(
        self,
        url: str,
        *,
        accept: dict[str, str] | None = None,
        use_ajax: bool = True,
    ) -> aiohttp.ClientResponse:
        """
        Perform an authenticated GET request against the Alarm.com API.

        Public because camera.py (a sibling module, not just internal callers)
        also needs this for fetching snapshot images - it was never actually
        private in practice, just named as if it were.
        """
        if use_ajax:
            self._sync_ajax_key(url)
        resp = await self.session.get(
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
        data: dict | None = None,
        json_body: dict | None = None,
    ) -> aiohttp.ClientResponse:
        if use_ajax:
            self._sync_ajax_key(url)
        kwargs: dict = {
            "headers": _build_headers(
                accept or ACCEPT_JSONAPI,
                self.ajax_key if use_ajax else None,
            ),
            "cookies": self._extra_cookies(),
            "allow_redirects": True,
        }
        if data is not None:
            kwargs["data"] = data
        if json_body is not None:
            kwargs["json"] = json_body

        resp = await self.session.post(url, **kwargs)
        self._extract_cookies(resp)
        resp.raise_for_status()
        return resp

    async def login(self) -> AuthResult:
        """Perform full scraper login."""
        if not self.password:
            raise ValueError("Password required for independent login")

        _LOGGER.debug("Loading login page...")
        resp = await self.get(f"{URL_BASE}login", accept=ACCEPT_HTML, use_ajax=False)
        html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")

        fields: dict[str, str] = {}
        for fid in (
            VIEWSTATE_FIELD,
            VIEWSTATEGENERATOR_FIELD,
            EVENTVALIDATION_FIELD,
            PREVIOUSPAGE_FIELD,
        ):
            el = soup.select_one(f"#{fid}")
            if el is None:
                raise RuntimeError(f"Could not find #{fid} in login page HTML")
            fields[fid] = str(el.attrs.get("value", ""))

        _LOGGER.debug("Submitting credentials...")
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
            raise RuntimeError("Login failed, bad username or password.")
        if "m=LockedOut" in url_str:
            raise RuntimeError("Account is locked out.")

        await self._load_identity()
        return await self._check_mfa()

    async def _load_identity(self) -> None:
        _LOGGER.debug("Loading user identity...")
        resp = await self.get(f"{API_URL_BASE}identities")
        body = await resp.json()
        data = body.get("data")

        if isinstance(data, list) and data:
            self.identity_id = data[0]["id"]
        elif isinstance(data, dict):
            self.identity_id = data["id"]
        else:
            raise RuntimeError("No identity data returned")

    async def _check_mfa(self) -> AuthResult:
        """Check MFA requirement."""
        _LOGGER.debug("Checking MFA requirements...")
        resp = await self.get(f"{API_URL_BASE}{TWO_FACTOR_PATH}/{self.identity_id}")
        body = await resp.json()
        attrs = body.get("data", {}).get("attributes", {})

        enabled_mask: int = attrs.get("enabledTwoFactorTypes", 0) or 0
        device_trusted: bool = attrs.get("isCurrentDeviceTrusted", False)

        if enabled_mask == 0 or device_trusted:
            _LOGGER.info("MFA not required (trusted device).")
            return AuthResult.SUCCESS

        _LOGGER.warning(
            "MFA required on camera session but no interactive "
            "prompt is available. This should not happen if the main integration "
            "has already trusted this device. Camera may be unavailable until "
            "the device is trusted via the main integration's re-auth flow."
        )
        self._pending_mfa_type = None
        return AuthResult.MFA_REQUIRED

    async def get_camera_list(self) -> list[dict]:
        """Return list of camera summary dicts."""
        resp = await self.get(f"{API_URL_BASE}video/devices/cameras")
        body = await resp.json()
        data = body.get("data", [])

        if isinstance(data, dict):
            data = [data]

        cameras: list[dict] = []
        for cam in data:
            attrs = cam.get("attributes", {})
            summary = {"id": cam.get("id")}
            summary.update(attrs)
            cameras.append(summary)

        return cameras

    async def get_snapshot_url(self, camera_id: str) -> str | None:
        """Request an ephemeral image URL, keeping it out of logs and HA state."""
        resp = await self.get(f"{API_URL_BASE}video/snapshots/{camera_id}")
        try:
            body = await resp.json()
        finally:
            resp.release()
        if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
            return None
        attributes = body["data"].get("attributes")
        if not isinstance(attributes, dict) or attributes.get("error"):
            return None
        url = attributes.get("url")
        return url if isinstance(url, str) and url else None

    async def get_stream_info(self, camera_id: str, *, preferred_transport: str = "endToEnd") -> dict | None:
        """
        Fetch WebRTC config for a camera.

        Important: do not swallow ClientResponseError here.
        camera.py needs 401/403 to bubble up so it can retry auth.
        """
        resp = await self.get(
            f"{API_URL_BASE}video/videoSources/liveVideoHighestResSources/{camera_id}"
        )
        body = await resp.json()

        # Stream responses contain short-lived authentication secrets. Never
        # emit raw responses, even when DEBUG logging is explicitly enabled.
        if _RAW_RESPONSE_LOGGER.isEnabledFor(logging.INFO):
            _RAW_RESPONSE_LOGGER.info(
                "get_stream_info response received for camera %s",
                camera_id,
            )

        top_attrs = body.get("data", {}).get("attributes", {})
        ice_servers_s = top_attrs.get("iceServers")

        try:
            ice_servers = json.loads(ice_servers_s) if ice_servers_s else []
        except Exception as err:
            _LOGGER.warning(
                "Failed to parse iceServers for camera %s: %s",
                camera_id,
                err,
            )
            ice_servers = []

        included = body.get("included", [])

        # Preserve the pre-2026.11.06 transport by default (#177), while letting
        # accounts affected by #172 prefer Janus without editing source files.
        end_to_end = next((item for item in included
                           if item.get("type") == "video/videoSources/endToEndWebrtcConnectionInfo"), None)
        has_janus = bool(top_attrs.get("janusGatewayUrl") and top_attrs.get("janusToken"))
        if end_to_end is not None and (preferred_transport != "janus" or not has_janus):
            config = dict(end_to_end.get("attributes", {}))
            config["iceServers"] = ice_servers
            config["streamType"] = "endToEnd"
            return config

        if top_attrs.get("janusGatewayUrl") and top_attrs.get("janusToken"):
            # Find the HD stream mountpoint ID from the quality message included items.
            # Alarm.com includes webrtcStreamQualityMessage entries with a streamID field;
            # the HD entry (id suffix "-Hd") carries the Janus mountpoint ID.
            janus_stream_id: int | None = None
            camera_id_hd = f"{camera_id}-Hd"
            for inc in included:
                if (
                    inc.get("type") == "video/videoSources/webrtcStreamQualityMessage"
                    and inc.get("id") == camera_id_hd
                ):
                    janus_stream_id = inc.get("attributes", {}).get("streamID")
                    break
            # Fall back to SD if HD not found
            if janus_stream_id is None:
                camera_id_sd = f"{camera_id}-Sd"
                for inc in included:
                    if (
                        inc.get("type") == "video/videoSources/webrtcStreamQualityMessage"
                        and inc.get("id") == camera_id_sd
                    ):
                        janus_stream_id = inc.get("attributes", {}).get("streamID")
                        break

            # Last resort: parse the numeric suffix from the camera ID itself.
            # e.g. "110353471-2048" → 2048. This is used for cameras that don't
            # include quality message entries in their API response.
            if janus_stream_id is None:
                try:
                    janus_stream_id = int(camera_id.rsplit("-", 1)[-1])
                    _LOGGER.debug(
                        "Derived Janus stream ID %s from camera ID suffix for camera %s",
                        janus_stream_id,
                        camera_id,
                    )
                except (ValueError, IndexError):
                    pass

            config = {
                "streamType": "janus",
                "janusGatewayUrl": top_attrs["janusGatewayUrl"],
                "janusToken": top_attrs["janusToken"],
                "janusStreamId": janus_stream_id,
                "proxyUrl": top_attrs.get("proxyUrl"),
                "iceServers": ice_servers,
            }
            _LOGGER.debug(
                "Found Janus proxy WebRTC config for camera %s (streamId=%s)",
                camera_id,
                janus_stream_id,
            )
            return config

        _LOGGER.debug(
            "No WebRTC config found for camera %s. "
            "errorEnum=%s, isMjpeg=%s, janusGatewayUrl=%s, "
            "janusToken=%s, proxyUrl=%s. "
            "included types: %s. Top-level keys: %s",
            camera_id,
            top_attrs.get("errorEnum"),
            top_attrs.get("isMjpeg"),
            "set" if top_attrs.get("janusGatewayUrl") else "empty",
            "set" if top_attrs.get("janusToken") else "empty",
            "set" if top_attrs.get("proxyUrl") else "empty",
            [inc.get("type") for inc in included],
            list(top_attrs.keys()),
        )
        return None

    async def close(self) -> None:
        """Close the HTTP session only if we own it."""
        if self._owns_session and self.session and not self.session.closed:
            await self.session.close()
