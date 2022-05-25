"""Alarmdotcom implementation of an HA light."""
from __future__ import annotations

from collections.abc import Callable
from enum import Enum
import logging
from typing import Any

from homeassistant import core
from homeassistant.components import light
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyalarmdotcomajax.devices import Light as pyadcLight

from .base_device import IntBaseDevice
from .const import DOMAIN

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the light platform."""

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        IntLight(
            coordinator=coordinator,
            device_data=coordinator.data.get("entity_data", {}).get(device_id),
        )
        for device_id in coordinator.data.get("light_ids", [])
    )


class IntLight(IntBaseDevice, LightEntity):  # type: ignore
    """Integration Light Entity."""

    _device_type_name: str = "Light"

    # class States(Enum):
    #     """Enum of light states."""

    #     ON = "ON"
    #     OFF = "OFF"
    class DataStructure(IntBaseDevice.DataStructure):
        """Dict for an ADCI Light."""

        brightness: int | None

        desired_state: Enum
        raw_state_text: str
        state: pyadcLight.DeviceState
        parent_id: str
        async_turn_on_callback: Callable
        async_turn_off_callback: Callable
        read_only: bool
        supports_state_tracking: bool

    def __init__(
        self, coordinator: DataUpdateCoordinator, device_data: DataStructure
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, device_data)

        self._device = device_data
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
            pyadcLight.DeviceState.ON,
            pyadcLight.DeviceState.LEVELCHANGE,
        ]:
            return True

        if self._device.get("state") == pyadcLight.DeviceState.OFF:
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

        await self.coordinator.async_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""

        try:
            await self.async_turn_off_callback()
        except PermissionError:
            self._show_permission_error("turn off")

        await self.coordinator.async_update()
