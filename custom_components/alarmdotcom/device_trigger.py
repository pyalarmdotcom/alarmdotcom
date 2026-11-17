"""
Device triggers for alarmdotcom, Z-Wave Central Scene actions on lights/switches.

Modelled on HA's Z-Wave JS "Scene action on Endpoint 0 Scene 00x" trigger:
pick the scene (Scene 001 = on/up paddle, Scene 002 = off/down paddle) and,
optionally, the value (KeyPressed, KeyPressed2x, KeyHeldDown, …). Leaving the
value empty triggers on any key action for that scene.

Triggers listen for the ``alarmdotcom_scene`` bus event fired by the event platform.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_SCENE, SCENE_ACTIONS
from .schema import vol

CONF_SUBTYPE = "subtype"
CONF_VALUE = "value"
TRIGGER_TYPE_SCENE_ACTION = "scene_action"
SUBTYPES = {f"scene_{scene:03d}": scene for scene in (1, 2)}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): TRIGGER_TYPE_SCENE_ACTION,
        vol.Required(CONF_SUBTYPE): vol.In(list(SUBTYPES)),
        vol.Optional(CONF_VALUE): vol.In(SCENE_ACTIONS),
    }
)


def _is_light_device(hass: HomeAssistant, device_id: str) -> bool:
    """Return True if the HA device is an Alarm.com light/switch."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return False
    resource_ids = {ident for domain, ident in device.identifiers if domain == DOMAIN}
    if not resource_ids:
        return False
    for entry in hass.config_entries.async_entries(DOMAIN):
        runtime = getattr(entry, "runtime_data", None)
        if runtime is None:
            continue
        lights = runtime.hub.api.lights
        if any(lights.get(resource_id) is not None for resource_id in resource_ids):
            return True
    return False


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List a "Scene action" trigger per scene for an Alarm.com light/switch."""
    if not _is_light_device(hass, device_id):
        return []
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: TRIGGER_TYPE_SCENE_ACTION,
            CONF_SUBTYPE: subtype,
        }
        for subtype in SUBTYPES
    ]


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """Offer the optional Value dropdown (KeyPressed, KeyPressed2x, …)."""
    return {
        "extra_fields": vol.Schema(
            {vol.Optional(CONF_VALUE): vol.In({v: v for v in SCENE_ACTIONS})}
        )
    }


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger that fires on the matching alarmdotcom_event."""
    event_data: dict[str, Any] = {
        CONF_DEVICE_ID: config[CONF_DEVICE_ID],
        "scene": SUBTYPES[config[CONF_SUBTYPE]],
    }
    if CONF_VALUE in config:
        event_data[CONF_VALUE] = config[CONF_VALUE]
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_SCENE,
            event_trigger.CONF_EVENT_DATA: event_data,
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
