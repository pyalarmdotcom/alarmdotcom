"""Camera platform for Alarm.com (WebRTC)."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from time import monotonic
from typing import TYPE_CHECKING, Any

import aiohttp
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from yarl import URL

from .const import (
    CONF_CAMERA_STREAM_TRANSPORT,
    CONF_CAMERA_TOKEN_REFRESH_INTERVAL,
    CONF_OPTIONS_DEFAULT,
    DOMAIN,
)

if TYPE_CHECKING:
    from .camera_api import AlarmCameraSession

# Entities are updated via push (websocket events), not per-entity polling -
# PARALLEL_UPDATES has no effect on update frequency here, but setting it
# to 0 is still the correct, explicit signal for a push-based integration.
PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)



async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alarm.com cameras from a config entry."""
    camera_session: AlarmCameraSession | None = entry.runtime_data.camera_session

    if camera_session is None:
        _LOGGER.debug(
            "No camera session available for entry %s, skipping camera setup.",
            entry.entry_id,
        )
        return

    try:
        login_generation = camera_session.session_generation
        cameras = await camera_session.get_camera_list()
    except aiohttp.ClientResponseError as err:
        if err.status in (401, 403):
            _LOGGER.warning("Camera list fetch unauthorized, attempting re-login.")
            try:
                await camera_session.ensure_login(login_generation)
                cameras = await camera_session.get_camera_list()
            except Exception as retry_err:
                # A failed retry must not propagate: this is a separate platform from
                # alarm_control_panel/sensor/etc, and accounts with no cameras configured
                # (or with a persistent camera-specific auth issue) should still get their
                # other entities. Previously an unhandled exception here could take down
                # camera setup - and, per reports, leave the rest of the integration's
                # entities unavailable too.
                _LOGGER.error(
                    "Camera list fetch failed after re-login attempt: %s. "
                    "Skipping camera setup; other entities are unaffected.",
                    retry_err,
                )
                return
        else:
            _LOGGER.error("Camera list fetch failed (%s), skipping.", err.status)
            return
    except Exception as err:
        _LOGGER.error("Camera list fetch failed: %s, skipping.", err)
        return

    if not cameras:
        _LOGGER.debug("No cameras found for entry %s, skipping camera setup.", entry.entry_id)
        return

    # User-configurable via the options flow (#93); the entry reloads on change.
    refresh_interval = timedelta(
        minutes=entry.options.get(
            CONF_CAMERA_TOKEN_REFRESH_INTERVAL,
            CONF_OPTIONS_DEFAULT[CONF_CAMERA_TOKEN_REFRESH_INTERVAL],
        )
    )

    async_add_entities(
        [
            AlarmDotComCamera(
                camera_session, cam, entry.entry_id, refresh_interval,
                preferred_transport=entry.options.get(
                    CONF_CAMERA_STREAM_TRANSPORT, CONF_OPTIONS_DEFAULT[CONF_CAMERA_STREAM_TRANSPORT]
                ),
            )
            for cam in cameras
        ]
    )


class AlarmDotComCamera(Camera):
    """Alarm.com WebRTC Camera entity."""

    _attr_has_entity_name = False
    _attr_supported_features = CameraEntityFeature.ON_OFF

    def __init__(
        self,
        session: AlarmCameraSession,
        info: dict,
        entry_id: str,
        token_refresh_interval: timedelta,
        *,
        preferred_transport: str = "endToEnd",
    ) -> None:
        """Initialize the camera."""
        super().__init__()
        self._session = session
        self._id = info["id"]
        self._name = info.get("description", self._id)
        self._entry_id = entry_id
        self._token_refresh_interval = token_refresh_interval
        self._preferred_transport = preferred_transport

        self._attr_unique_id = f"{entry_id}_camera_{self._id}"
        self._attr_name = self._name
        self._webrtc_config: dict | None = None
        self._last_empty_stream_warning: float | None = None
        self._remove_refresh: CALLBACK_TYPE | None = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"camera_{self._id}")},
            name=self._name,
            manufacturer="Alarm.com",
            model=info.get("deviceModel"),
            sw_version=info.get("firmwareVersion"),
        )

        self._fetch_lock = asyncio.Lock()

    async def async_added_to_hass(self) -> None:
        """Start periodic token refresh when entity is added."""
        await super().async_added_to_hass()
        self.hass.data.setdefault(DOMAIN + '_camera_entities', {})[self.entity_id] = self

        await self._fetch_stream_info()

        self._remove_refresh = async_track_time_interval(
            self.hass,
            self._async_refresh_tokens,
            self._token_refresh_interval,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel periodic refresh when entity is removed."""
        self.hass.data.get(DOMAIN + '_camera_entities', {}).pop(self.entity_id, None)
        if self._remove_refresh is not None:
            self._remove_refresh()
            self._remove_refresh = None

    async def _async_refresh_tokens(self, _now: Any = None) -> None:
        """Refresh WebRTC tokens unconditionally."""
        _LOGGER.debug("Refreshing WebRTC tokens for camera %s", self._id)
        await self._fetch_stream_info()

    async def _fetch_stream_info(self) -> None:
        """Fetch stream info from Alarm.com with one auth retry."""
        if self._fetch_lock.locked():
            _LOGGER.debug(
                "Waiting for token fetch already in progress for camera %s.",
                self._id,
            )
            # Share the in-flight result rather than returning stale credentials.
            async with self._fetch_lock:
                pass
            return

        async with self._fetch_lock:
            try:
                login_generation = self._session.session_generation
                config = await self._session.get_stream_info(self._id, preferred_transport=self._preferred_transport)

            except aiohttp.ClientResponseError as err:
                if err.status in (401, 403):
                    _LOGGER.info(
                        "WebRTC auth failure for camera %s (HTTP %s), re-authenticating.",
                        self._id,
                        err.status,
                    )
                    try:
                        if self._session.owns_session:
                            # self._fetch_lock only guards this one camera entity.
                            # All cameras on this config entry share one AlarmCameraSession,
                            # so ensure_login() (rather than login() directly) is required
                            # here: it lets concurrent cameras hitting this same 401/403 at
                            # the same moment collapse into a single real login instead of
                            # each independently re-authenticating.
                            await self._session.ensure_login(login_generation)
                        else:
                            # Normal case: this camera is on the session shared with the
                            # AlarmBridge (owns_session=False). repair_shared_session()
                            # coordinates the swap to an independent session across all
                            # cameras sharing it, so only one real login happens even
                            # though all cameras' refresh timers tend to fire together.
                            self._session = await self._session.repair_shared_session(
                                login_generation
                            )

                        config = await self._session.get_stream_info(self._id, preferred_transport=self._preferred_transport)

                    except Exception as retry_err:
                        _LOGGER.error(
                            "WebRTC re-login failed for camera %s: %s",
                            self._id,
                            retry_err,
                        )
                        self._webrtc_config = None
                        self.async_write_ha_state()
                        return
                else:
                    _LOGGER.error(
                        "WebRTC token fetch failed for camera %s: HTTP %s",
                        self._id,
                        err.status,
                    )
                    self._webrtc_config = None
                    self.async_write_ha_state()
                    return

            except Exception as err:
                _LOGGER.error(
                    "WebRTC token fetch error for camera %s: %s",
                    self._id,
                    err,
                )
                self._webrtc_config = None
                self.async_write_ha_state()
                return

            if not config:
                now = monotonic()
                if (self._last_empty_stream_warning is None
                        or now - self._last_empty_stream_warning >= 1800):
                    _LOGGER.warning("Empty stream info returned for camera %s", self._id)
                    self._last_empty_stream_warning = now
                self._webrtc_config = None
            else:
                self._webrtc_config = config
                self._last_empty_stream_warning = None
                _LOGGER.debug("WebRTC tokens refreshed for camera %s", self._id)

            self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if we have a valid WebRTC config."""
        return self._webrtc_config is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Never expose ephemeral stream credentials in HA state or recorder."""
        return {}

    async def async_get_webrtc_config(self) -> dict | None:
        """
        Fetch current credentials for a new authorized browser session.

        Cached credentials may have expired or been consumed by a previous
        stream. Dashboard reconnects must not depend on the periodic refresh.
        Concurrent callers share a fetch already in progress for this camera.
        """
        await self._fetch_stream_info()
        return self._webrtc_config

    async def stream_source(self) -> str | None:
        """
        Return a native HA stream source.

        Alarm.com cameras use WebRTC configuration retrieved via an
        authenticated websocket command, not a native HLS or RTSP URL.
        Returning None prevents Home Assistant from treating the config dict
        like a native stream object.
        """
        return None

    async def async_turn_on(self) -> None:
        """Fetch fresh WebRTC tokens on demand."""
        await self._fetch_stream_info()

    async def async_turn_off(self) -> None:
        """Clear the WebRTC config."""
        self._webrtc_config = None
        self.async_write_ha_state()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still snapshot image from the camera."""
        try:
            signed_url = await self._session.get_snapshot_url(self._id)
            if not signed_url:
                return None
            url = URL(signed_url)
            if url.scheme != "https" or not url.host or url.user is not None:
                return None

            # The signed URL belongs to a video host, not the authenticated API.
            # A separate cookie-free client prevents session cookies, MFA tokens,
            # and AJAX headers from being forwarded with the image request.
            async with aiohttp.ClientSession(
                cookie_jar=aiohttp.DummyCookieJar(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as image_session, image_session.get(url, allow_redirects=False) as response:
                response.raise_for_status()
                if response.status != 200 or not response.content_type.startswith("image/"):
                    return None
                # Bound the download and do not return HTML/JSON error pages
                # as a successful camera snapshot.
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.content.iter_chunked(64 * 1024):
                    size += len(chunk)
                    if size > 10 * 1024 * 1024:
                        return None
                    chunks.append(chunk)
                return b"".join(chunks) or None
        except aiohttp.ClientResponseError as err:
            _LOGGER.debug("Snapshot request failed with HTTP %s", err.status)
        except Exception as err:
            # Exceptions can contain signed URLs. Log only the exception type.
            _LOGGER.debug("Snapshot request failed (%s)", type(err).__name__)

        return None
