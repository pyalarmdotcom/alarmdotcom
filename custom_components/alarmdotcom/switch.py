"""Alarmdotcom implementation of an HA switch."""
from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant import core
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyalarmdotcomajax.extensions import (
    CameraSkybellControllerExtension as pyadcCameraSkybellControllerExtension,
)
from pyalarmdotcomajax.extensions import (
    ConfigurationOption as pyadcConfigurationOption,
)
from pyalarmdotcomajax.extensions import (
    ConfigurationOptionType as pyadcConfigurationOptionType,
)

from .base_device import IntBaseDevice
from .base_device import IntConfigEntityDataStructure
from .const import DOMAIN

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        IntConfigSwitch(
            coordinator=coordinator,
            device_data=coordinator.data.get("entity_data", {}).get(device_id),
        )
        for device_id in coordinator.data.get("config_switch_ids", [])
    )


class IntConfigSwitch(IntBaseDevice, SwitchEntity):  # type: ignore
    """Integration Number Entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_data: IntConfigEntityDataStructure,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, device_data)

        self._device = device_data
        self._config_option: pyadcConfigurationOption = self._device.get(
            "config_option", {}
        )

        self._attr_entity_category = EntityCategory.CONFIG

        try:
            self.async_change_setting_callback: Callable = self._device[
                "async_change_setting_callback"
            ]
        except KeyError:
            log.error("Failed to initialize control functions for %s.", self.unique_id)
            self._attr_available = False

        log.debug(
            "%s: Initializing Alarm.com configuration entity for %s.",
            __name__,
            self.unique_id,
        )

    @property
    def is_on(self) -> bool:
        """Return the entity value to represent the entity state."""

        return (
            self._config_option.get("current_value")
            is pyadcCameraSkybellControllerExtension.ChimeOnOff.ON
        )

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if (
            self._config_option.get("option_type")
            is pyadcConfigurationOptionType.BINARY_CHIME
        ):
            return "mdi:bell" if self.is_on else "mdi:bell-off"

        return super().icon if isinstance(super().icon, str) else None

    @property
    def device_info(self) -> dict:
        """Return info to categorize this entity as a device."""

        # Associate with parent device.
        return {
            "identifiers": {(DOMAIN, self._device.get("parent_id"))},
        }

    async def async_turn_on(self, **kwargs) -> None:  # type: ignore
        """Turn on."""
        await self.async_change_setting_callback(
            self._config_option.get("slug"),
            pyadcCameraSkybellControllerExtension.ChimeOnOff.ON,
        )

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore
        """Turn off."""
        await self.async_change_setting_callback(
            self._config_option.get("slug"),
            pyadcCameraSkybellControllerExtension.ChimeOnOff.OFF,
        )

        await self.coordinator.async_refresh()
