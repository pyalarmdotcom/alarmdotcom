"""Z-Wave Central Scene entities for Alarm.com lights and switches."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from _pyalarmdotcomajax.events import DeviceActivityMessage, EventBrokerTopic
from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_SCENE, SCENE_ACTIONS
from .entity import device_info_fn

if TYPE_CHECKING:
    from .hub import AlarmHub


def decode_scene(value: float | None) -> tuple[int, str] | None:
    """Unpack ADC's 10000 * key attribute + scene number encoding."""
    if value is None or not value.is_integer() or value <= 0:
        return None
    key_attribute, scene = divmod(int(value), 10000)
    if scene not in (1, 2) or key_attribute >= len(SCENE_ACTIONS):
        return None
    return scene, SCENE_ACTIONS[key_attribute]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    """Expose two paddle events per light and one shared automation bus publisher."""
    hub = entry.runtime_data.hub
    async_add_entities(AdcSceneEvent(hub, light.id, scene) for light in hub.api.lights for scene in (1, 2))

    @callback
    def publish_scene(message: Any) -> None:
        # Only known light IDs can create a scene event. A zone with the same
        # event number must never trigger a switch automation.
        if not isinstance(message, DeviceActivityMessage) or message.event_type != 163:
            return
        if hub.api.lights.get(message.id) is None or (decoded := decode_scene(message.value)) is None:
            return
        device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, message.id), entry.entry_id)
        if device is not None:
            scene, action = decoded
            hass.bus.async_fire(EVENT_SCENE, {
                "device_id": device.id, "resource_id": message.id, "scene": scene, "value": action,
            })

    entry.async_on_unload(hub.api.events.subscribe(EventBrokerTopic.DEVICE_ACTIVITY, publish_scene))


class AdcSceneEvent(EventEntity):
    """Timestamped paddle action with the standard Z-Wave event names."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:gesture-tap-button"

    def __init__(self, hub: AlarmHub, resource_id: str, scene: int) -> None:
        """Keep the existing light's device identity."""
        self._attr_event_types = list(SCENE_ACTIONS)
        self._hub = hub
        self._resource_id = resource_id
        self._scene = scene
        self._attr_unique_id = f"{resource_id}_scene_{scene:03d}"
        self._attr_name = f"Scene {scene:03d}"
        self._attr_device_info = device_info_fn(hub, resource_id, None)

    @property
    def available(self) -> bool:
        """Unavailable when its light has been removed or the hub is offline."""
        return self._hub.available and self._hub.api.lights.get(self._resource_id) is not None

    async def async_added_to_hass(self) -> None:
        """Unsubscribe automatically when the entity is removed."""
        await super().async_added_to_hass()
        self.async_on_remove(self._hub.api.events.subscribe(
            EventBrokerTopic.DEVICE_ACTIVITY, self._handle_activity, ids=self._resource_id,
        ))

    @callback
    def _handle_activity(self, message: Any) -> None:
        """Record repeated identical presses as separate events."""
        if not isinstance(message, DeviceActivityMessage) or message.event_type != 163:
            return
        decoded = decode_scene(message.value)
        if decoded is not None and decoded[0] == self._scene:
            self._trigger_event(decoded[1])
            self.async_write_ha_state()
