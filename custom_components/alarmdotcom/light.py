"""Interfaces with Alarm.com lights."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Literal

import _pyalarmdotcomajax as pyadc
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .entity import AdcControllerT, AdcEntity, AdcEntityDescription, AdcManagedDeviceT
from .util import cleanup_orphaned_entities_and_devices

if TYPE_CHECKING:
    from .auto_off import AutoOffManager
    from .hub import AlarmHub

BRIGHTNESS_SCALE = (1, 99)
# ADC reports white warmth as a percentage rather than physical Kelvin bounds.
# Map that relative range onto HA's conventional white-light slider.
MIN_COLOR_TEMP_KELVIN = 2700
MAX_COLOR_TEMP_KELVIN = 6500

# Entities are updated via push (websocket events), not per-entity polling -
# PARALLEL_UPDATES has no effect on update frequency here, but setting it
# to 0 is still the correct, explicit signal for a push-based integration.
PARALLEL_UPDATES = 0

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the light platform."""

    hub: AlarmHub = config_entry.runtime_data.hub
    auto_off_manager: AutoOffManager = config_entry.runtime_data.auto_off_manager

    entities: list[AdcLightEntity] = [
        AdcLightEntity(
            hub=hub, resource_id=device.id, description=entity_description, auto_off_manager=auto_off_manager
        )
        for entity_description in ENTITY_DESCRIPTIONS
        for device in hub.api.lights
        if entity_description.supported_fn(hub, device.id)
    ]
    async_add_entities(entities)

    current_entity_ids = {entity.entity_id for entity in entities}
    current_unique_ids = {uid for uid in (entity.unique_id for entity in entities) if uid is not None}
    await cleanup_orphaned_entities_and_devices(hass, config_entry, current_entity_ids, current_unique_ids, "light")


@callback
def is_on_fn(hub: AlarmHub, light_id: str) -> bool:
    """Return whether the light is on."""

    resource = hub.api.lights[light_id]
    return resource.attributes.state in (pyadc.light.LightState.ON, pyadc.light.LightState.LEVEL_CHANGE)


@callback
def brightness_fn(hub: AlarmHub, light_id: str) -> int | None:
    """Return the brightness of the light."""

    resource = hub.api.lights[light_id]
    return value_to_brightness(BRIGHTNESS_SCALE, resource.attributes.light_level)


@callback
def supported_features_fn(controller: pyadc.LightController, light_id: str) -> LightEntityFeature:
    """Return the supported features for the light."""

    # We don't support light entity features yet.

    return LightEntityFeature(0)


@callback
def color_mode_fn(hub: AlarmHub, light_id: str) -> ColorMode:
    """Return the color mode of the light."""

    resource = hub.api.lights.get(light_id)
    if resource is None:
        return ColorMode.UNKNOWN

    if resource.attributes.light_color_format == pyadc.light.LightColorFormat.WARM_TO_COOL and resource.attributes.supports_white_light_color_control:
        return ColorMode.COLOR_TEMP
    modes = supported_color_modes_fn(hub.api.lights, light_id)
    if ColorMode.RGB in modes:
        return ColorMode.RGB
    return next(iter(modes))


@callback
def supported_color_modes_fn(controller: pyadc.LightController, light_id: str) -> set[ColorMode]:
    """Return the supported color modes for the light."""

    resource = controller.get(light_id)
    if resource is None:
        return {ColorMode.UNKNOWN}

    modes = set()
    if resource.attributes.supports_rgb_color_control:
        modes.add(ColorMode.RGB)
    if resource.attributes.supports_white_light_color_control:
        modes.add(ColorMode.COLOR_TEMP)
    return modes or ({ColorMode.BRIGHTNESS} if resource.attributes.is_dimmer else {ColorMode.ONOFF})


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
            if brightness == 0:
                await controller.turn_off(light_id)
                return
            if brightness is not None:
                await controller.set_brightness(light_id, math.ceil(brightness_to_value(BRIGHTNESS_SCALE, brightness)))
            else:
                await controller.turn_on(light_id)
            if (rgb := options.get(ATTR_RGB_COLOR)) is not None:
                await controller.set_color(light_id, hex_color="#{:02X}{:02X}{:02X}".format(*rgb))
            elif (kelvin := options.get(ATTR_COLOR_TEMP_KELVIN)) is not None:
                fraction = (MAX_COLOR_TEMP_KELVIN - kelvin) / (MAX_COLOR_TEMP_KELVIN - MIN_COLOR_TEMP_KELVIN)
                await controller.set_color(light_id, percent_warmth=round(max(0, min(1, fraction)) * 100))
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


ENTITY_DESCRIPTIONS: list[AdcLightEntityDescription[pyadc.light.Light, pyadc.LightController]] = [
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
    _attr_min_color_temp_kelvin = MIN_COLOR_TEMP_KELVIN
    _attr_max_color_temp_kelvin = MAX_COLOR_TEMP_KELVIN

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Decode the current RGB hex value without discarding invalid updates."""
        value = self.controller[self.resource_id].attributes.hex_color
        if not isinstance(value, str) or len(value.lstrip("#")) != 6:
            return None
        try:
            return tuple(bytes.fromhex(value.lstrip("#")))
        except ValueError:
            return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Represent ADC's relative white warmth on the HA slider."""
        warmth = self.controller[self.resource_id].attributes.percent_warmth
        return round(MAX_COLOR_TEMP_KELVIN - max(0, min(100, warmth)) / 100 * (MAX_COLOR_TEMP_KELVIN - MIN_COLOR_TEMP_KELVIN))

    def __init__(
        self,
        hub: AlarmHub,
        resource_id: str,
        description: AdcLightEntityDescription,
        auto_off_manager: AutoOffManager,
    ) -> None:
        """Initialize the light entity, additionally wiring in the auto-off manager."""

        self._auto_off_manager = auto_off_manager
        super().__init__(hub=hub, resource_id=resource_id, description=description)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """
        Return this entity's extra attributes, plus a live auto_off_at if a timer is pending.

        auto_off_at is deliberately computed live here (not set once in
        __init__ like the rest of this entity's state) since it needs to
        reflect whatever the auto-off manager currently has scheduled,
        which can change at any time via the set_auto_off/cancel_auto_off
        services - not just on the resource-update events the rest of this
        entity's state responds to.
        """

        attrs = dict(self._attr_extra_state_attributes or {})
        if self.entity_id and (off_at := self._auto_off_manager.get_off_at(self.entity_id)) is not None:
            attrs["auto_off_at"] = off_at.isoformat()
        return attrs

    @callback
    def initiate_state(self) -> None:
        """Initiate entity state."""

        self._attr_is_on = self.entity_description.is_on_fn(self.hub, self.resource_id)
        self._attr_brightness = self.entity_description.brightness_fn(self.hub, self.resource_id)
        self._attr_supported_features = self.entity_description.supported_features_fn(self.controller, self.resource_id)
        self._attr_supported_color_modes = self.entity_description.supported_color_modes_fn(
            self.controller, self.resource_id
        )
        self._attr_color_mode = self.entity_description.color_mode_fn(self.hub, self.resource_id)

        super().initiate_state()

    @callback
    def update_state(self, message: pyadc.EventBrokerMessage | None = None) -> None:
        """Update entity state."""

        if isinstance(message, pyadc.ResourceEventMessage):
            self._attr_is_on = self.entity_description.is_on_fn(self.hub, self.resource_id)
            self._attr_brightness = self.entity_description.brightness_fn(self.hub, self.resource_id)
            self._attr_color_mode = self.entity_description.color_mode_fn(self.hub, self.resource_id)

            # entity_id is only set once this entity has actually been added
            # to hass - not during the initial initiate_state() call inside
            # __init__, which is why this lives here and not there.
            if self.entity_id:
                self._auto_off_manager.notify_state_changed_externally(self.entity_id, is_on=self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""

        await self.entity_description.control_fn(self.controller, self.resource_id, "turn_on", kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""

        await self.entity_description.control_fn(self.controller, self.resource_id, "turn_off", kwargs)
