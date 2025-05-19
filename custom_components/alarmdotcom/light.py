"""Interfaces with Alarm.com lights."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Literal

import pyalarmdotcomajax as pyadc
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DATA_HUB, DOMAIN
from .entity import AdcControllerT, AdcEntity, AdcEntityDescription, AdcManagedDeviceT
from .util import cleanup_orphaned_entities_and_devices

if TYPE_CHECKING:
    from .hub import AlarmHub

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the light platform."""

    hub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id][DATA_HUB]

    entities = [
        AdcLightEntity(hub=hub, resource_id=device.id, description=entity_description)
        for entity_description in ENTITY_DESCRIPTIONS
        for device in hub.api.lights
        if entity_description.supported_fn(hub, device.id)
    ]
    async_add_entities(entities)

    current_entity_ids = {entity.entity_id for entity in entities}
    current_unique_ids = {
        uid for uid in (entity.unique_id for entity in entities) if uid is not None
    }
    await cleanup_orphaned_entities_and_devices(
        hass, config_entry, current_entity_ids, current_unique_ids, "light"
    )


@callback
def is_on_fn(hub: AlarmHub, light_id: str) -> bool:
    """Return whether the light is on."""

    resource = hub.api.lights[light_id]
    return resource.attributes.state == pyadc.light.LightState.ON


@callback
def brightness_fn(hub: AlarmHub, light_id: str) -> int | None:
    """Return the brightness of the light."""

    resource = hub.api.lights[light_id]
    return resource.attributes.light_level


@callback
def supported_features_fn(
    controller: pyadc.LightController, light_id: str
) -> LightEntityFeature:
    """Return the supported features for the light."""

    # We don't support light entity features yet.

    return LightEntityFeature(0)


@callback
def color_mode_fn(hub: AlarmHub, light_id: str) -> ColorMode:
    """Return the color mode of the light."""

    resource = hub.api.lights.get(light_id)
    if resource is None:
        return ColorMode.UNKNOWN

    return ColorMode.BRIGHTNESS if resource.attributes.is_dimmer else ColorMode.ONOFF


@callback
def supported_color_modes_fn(
    controller: pyadc.LightController, light_id: str
) -> set[ColorMode]:
    """Return the supported color modes for the light."""

    resource = controller.get(light_id)
    if resource is None:
        return {ColorMode.UNKNOWN}

    return (
        {ColorMode.BRIGHTNESS} if resource.attributes.is_dimmer else {ColorMode.ONOFF}
    )


@callback
async def control_fn(
    controller: pyadc.LightController,
    light_id: str,
    command: Literal["turn_on", "turn_off"],
    options: dict[str, Any],
) -> None:
    """Turn the light on or off."""

    brightness = options.get(ATTR_BRIGHTNESS)

    try:
        if command == "turn_on":
            if brightness is not None:
                await controller.set_brightness(light_id, brightness)
            else:
                await controller.turn_on(light_id, brightness=brightness)
        elif command == "turn_off":
            await controller.turn_off(light_id)
        else:
            raise ValueError(f"Unsupported command: {command}")
    except (pyadc.ServiceUnavailable, pyadc.UnexpectedResponse) as err:
        log.error("Failed to execute light command: %s", err)
        raise


@dataclass(frozen=True, kw_only=True)
class AdcLightEntityDescription(
    Generic[AdcManagedDeviceT, AdcControllerT],
    AdcEntityDescription[AdcManagedDeviceT, AdcControllerT],
    LightEntityDescription,
):
    """Base Alarm.com light entity description."""

    is_on_fn: Callable[[AlarmHub, str], bool]
    """Return whether the light is on."""
    brightness_fn: Callable[[AlarmHub, str], int | None]
    """Return the brightness of the light."""
    color_mode_fn: Callable[[AlarmHub, str], ColorMode]
    """Return the color mode of the light."""
    supported_features_fn: Callable[[AdcControllerT, str], LightEntityFeature]
    """Return the supported features for the light."""
    control_fn: Callable[
        [AdcControllerT, str, Literal["turn_on", "turn_off"], dict[str, Any]],
        Coroutine[Any, Any, None],
    ]
    supported_color_modes_fn: Callable[[AdcControllerT, str], set[ColorMode]]
    """Turn the light on or off."""


ENTITY_DESCRIPTIONS: list[
    AdcLightEntityDescription[pyadc.light.Light, pyadc.LightController]
] = [
    AdcLightEntityDescription(
        key="lights",
        controller_fn=lambda hub, _: hub.api.lights,
        is_on_fn=is_on_fn,
        brightness_fn=brightness_fn,
        supported_features_fn=supported_features_fn,
        control_fn=control_fn,
        supported_color_modes_fn=supported_color_modes_fn,
        color_mode_fn=color_mode_fn,
    )
]


class AdcLightEntity(AdcEntity[AdcManagedDeviceT, AdcControllerT], LightEntity):
    """Base Alarm.com light entity."""

    entity_description: AdcLightEntityDescription

    @callback
    def initiate_state(self) -> None:
        """Initiate entity state."""

        self._attr_is_on = self.entity_description.is_on_fn(self.hub, self.resource_id)
        self._attr_brightness = self.entity_description.brightness_fn(
            self.hub, self.resource_id
        )
        self._attr_supported_features = self.entity_description.supported_features_fn(
            self.controller, self.resource_id
        )
        self._attr_supported_color_modes = (
            self.entity_description.supported_color_modes_fn(
                self.controller, self.resource_id
            )
        )
        self._attr_color_mode = self.entity_description.color_mode_fn(
            self.hub, self.resource_id
        )

        super().initiate_state()

    @callback
    def update_state(self, message: pyadc.EventBrokerMessage | None = None) -> None:
        """Update entity state."""

        if isinstance(message, pyadc.ResourceEventMessage):
            self._attr_is_on = self.entity_description.is_on_fn(
                self.hub, self.resource_id
            )
            self._attr_brightness = self.entity_description.brightness_fn(
                self.hub, self.resource_id
            )
            self._attr_color_mode = self.entity_description.color_mode_fn(
                self.hub, self.resource_id
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""

        await self.entity_description.control_fn(
            self.controller, self.resource_id, "turn_on", kwargs
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""

        await self.entity_description.control_fn(
            self.controller, self.resource_id, "turn_off", kwargs
        )
