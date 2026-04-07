"""Camera platform for Alarm.com WebRTC cameras and doorbells."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

if TYPE_CHECKING:
    from .camera_api import AlarmCameraSession

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alarm.com camera entities."""

    hub_data = hass.data[DOMAIN][config_entry.entry_id]
    camera_session: AlarmCameraSession = hub_data["camera_session"]

    try:
        cameras = await camera_session.get_camera_list()
    except Exception:
        log.warning("Failed to discover Alarm.com cameras. Retrying with fresh login...")
        try:
            await camera_session.login()
            cameras = await camera_session.get_camera_list()
        except Exception:
            log.error("Could not discover Alarm.com cameras. Camera platform will not be loaded.")
            return

    if not cameras:
        log.info("No Alarm.com cameras found.")
        return

    entities = [AdcCamera(camera_session, cam, config_entry.entry_id) for cam in cameras]
    async_add_entities(entities)
    log.info("Added %s Alarm.com camera(s).", len(entities))


class AdcCamera(Camera):
    """Alarm.com WebRTC camera entity."""

    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.ON_OFF

    def __init__(
        self,
        session: AlarmCameraSession,
        info: dict[str, Any],
        entry_id: str,
    ) -> None:
        """Initialize the camera."""

        super().__init__()
        self._session = session
        self._camera_id: str = info["id"]
        self._camera_name: str = info.get("description", self._camera_id)
        self._webrtc_config: dict[str, Any] | None = None

        self._attr_unique_id = f"{entry_id}_{self._camera_id}"
        self._attr_name = self._camera_name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._camera_id)},
            name=self._camera_name,
            manufacturer="Alarm.com",
            model=info.get("deviceModel"),
            sw_version=info.get("firmwareVersion"),
        )

    @property
    def is_on(self) -> bool:
        """Return true if camera stream is active."""

        return self._webrtc_config is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return WebRTC configuration as state attributes."""

        return {"webrtc_config": self._webrtc_config}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Fetch WebRTC stream tokens."""

        try:
            config = await self._session.get_stream_info(self._camera_id)
            if not config:
                log.info("Stream info empty for %s, attempting re-login...", self._camera_name)
                await self._session.login()
                config = await self._session.get_stream_info(self._camera_id)

            self._webrtc_config = config
            self.async_write_ha_state()

        except Exception:
            log.exception("Failed to fetch WebRTC config for %s.", self._camera_name)
            self._webrtc_config = None
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Clear WebRTC stream tokens."""

        self._webrtc_config = None
        self.async_write_ha_state()

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Return a still image (not supported for WebRTC cameras)."""

        return None
