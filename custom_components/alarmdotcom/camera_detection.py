"""
Momentary object classification sensors from Alarm.com camera events.

Classification IDs and query-string names follow the HA-ADC/pyadc camera
implementation. Only confirmed detection events are accepted; changing an
analytics rule must not look like a person arriving.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs

from _pyalarmdotcomajax.events import DeviceActivityMessage, EventBrokerTopic
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

if TYPE_CHECKING:
    from .hub import AlarmHub

CATEGORY_NAMES = {
    "human": "person", "familiarface": "person", "unknownface": "person",
    "vehicle": "vehicle", "familiarvehicle": "vehicle", "deliveryvehicle": "vehicle",
    "animal": "animal", "parcel": "package",
}
CATEGORY_IDS = {0: "person", 104: "person", 105: "person", 1: "vehicle", 102: "vehicle", 103: "vehicle", 101: "animal", 4: "package"}
DETECTION_CLEAR_SECONDS = 10
_LOGGER = logging.getLogger(__name__)


def detected_objects(event_type: int, extra: str) -> set[str]:
    """Decode named classifications or numeric analytics categories."""
    fields = parse_qs(extra.lstrip("?"))
    if event_type == 71:
        return {CATEGORY_NAMES[name.strip().lower()] for value in fields.get("cnff", [])
                for name in value.split(",") if name.strip().lower() in CATEGORY_NAMES}
    result = set()
    if event_type == 210:
        for value in fields.get("category", []):
            try:
                category = int(value)
            except ValueError:
                continue
            if category in CATEGORY_IDS:
                result.add(CATEGORY_IDS[category])
    return result


@callback
def log_camera_detection(message: Any) -> None:
    """Log only the event type and allowlisted object classes."""
    if (
        not _LOGGER.isEnabledFor(logging.DEBUG)
        or not isinstance(message, DeviceActivityMessage)
        or message.event_type not in (71, 210)
    ):
        return
    classifications = detected_objects(message.event_type, message.extra)
    _LOGGER.debug(
        "Camera analytics event type=%s classifications=%s",
        message.event_type,
        ", ".join(sorted(classifications)) or "none",
    )


class CameraDetectionSensor(BinarySensorEntity):
    """A classification pulse, extended by each subsequent detection."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_is_on = False

    def __init__(self, hub: AlarmHub, resource_id: str, classification: str) -> None:
        """Attach to the existing camera device without changing its entity ID."""
        self._hub = hub
        self._resource_id = resource_id
        self._classification = classification
        self._cancel_clear: CALLBACK_TYPE | None = None
        self._attr_unique_id = f"{resource_id}_{classification}_detected"
        self._attr_name = f"{classification.title()} detected"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"camera_{resource_id}")})

    @property
    def available(self) -> bool:
        """Do not report usable analytics after the camera disappears."""
        return self._hub.available

    async def async_added_to_hass(self) -> None:
        """Listen only for this camera and release both subscriptions and timers."""
        await super().async_added_to_hass()
        self.async_on_remove(self._hub.api.events.subscribe(
            EventBrokerTopic.DEVICE_ACTIVITY, self._handle_activity, ids=self._resource_id,
        ))
        self.async_on_remove(self._stop_timer)

    @callback
    def _stop_timer(self) -> None:
        """Cancel a pending clear during unload or a repeated detection."""
        if self._cancel_clear is not None:
            self._cancel_clear()
            self._cancel_clear = None

    @callback
    def _handle_activity(self, message: Any) -> None:
        """Refresh the pulse only for this sensor's classification."""
        if not isinstance(message, DeviceActivityMessage):
            return
        if self._classification not in detected_objects(message.event_type, message.extra):
            return
        self._stop_timer()
        self._attr_is_on = True
        self.async_write_ha_state()
        self._cancel_clear = async_call_later(self.hass, DETECTION_CLEAR_SECONDS, self._clear)

    @callback
    def _clear(self, _now: Any) -> None:
        """End the pulse without requiring a nonexistent ADC clear event."""
        self._cancel_clear = None
        self._attr_is_on = False
        self.async_write_ha_state()
