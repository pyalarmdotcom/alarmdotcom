"""Alarmdotcom implementation of an HA light."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant import core
from homeassistant.components import light
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from pyalarmdotcomajax.entities import ADCLight

from . import ADCIEntity
from . import const as adci
from .controller import ADCIController

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    controller: ADCIController = hass.data[adci.DOMAIN][config_entry.entry_id]

    async_add_entities(
        ADCILight(controller, controller.devices.get("entity_data", {}).get(light_id))  # type: ignore
        for light_id in controller.devices.get("light_ids", [])
    )


class ADCILight(ADCIEntity, LightEntity):  # type: ignore
    """Integration Light Entity."""

    def __init__(
        self, controller: ADCIController, device_data: adci.ADCILightData
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(controller, device_data)

        self._device: adci.ADCILightData = device_data
        self._attr_supported_color_modes = (
            [light.COLOR_MODE_BRIGHTNESS]
            if self._device.get("brightness")
            else [light.COLOR_MODE_ONOFF]
        )
        self._attr_supported_features = light.SUPPORT_BRIGHTNESS
        self._attr_color_mode = (
            light.COLOR_MODE_BRIGHTNESS
            if self._device.get("brightness")
            else light.COLOR_MODE_ONOFF
        )

        try:
            self.async_turn_on_callback: Callable = self._device[
                "async_turn_on_callback"
            ]
            self.async_turn_off_callback: Callable = self._device[
                "async_turn_off_callback"
            ]
        except KeyError:
            log.error("Failed to initialize control functions for %s.", self.unique_id)
            self._attr_available = False

        log.debug(
            "%s: Initializing Alarm.com light entity for light %s.",
            __name__,
            self.unique_id,
        )

    @property
    def assumed_state(self) -> bool:
        """Return whether device reports state."""

        return not self._device.get("supports_state_tracking", False)

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        if self._device.get("state") in [
            ADCLight.DeviceState.ON,
            ADCLight.DeviceState.LEVELCHANGE,
        ]:
            return True

        if self._device.get("state") == ADCLight.DeviceState.OFF:
            return False

        log.error(
            "Cannot determine light state. Found raw state of %s.",
            self._device.get("state"),
        )

        return None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return entity specific state attributes."""

        return {"mac_address": self._device.get("mac_address")}

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""

        if raw_bright := self._device.get("brightness"):
            return int((raw_bright * 255) / 100)

        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light or adjust brightness."""

        brightness: int | None = None
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int((kwargs[ATTR_BRIGHTNESS] / 255) * 100)

        try:
            await self.async_turn_on_callback(brightness)
        except PermissionError:
            self._show_permission_error("turn on")

        await self._controller.async_coordinator_update(critical=False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""

        try:
            await self.async_turn_off_callback()
        except PermissionError:
            self._show_permission_error("turn off")

        await self._controller.async_coordinator_update(critical=False)
