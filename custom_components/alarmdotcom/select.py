"""Alarmdotcom implementation of an HA switch."""
from __future__ import annotations

from collections.abc import Callable
from enum import Enum
import logging

from homeassistant import core
from homeassistant.components.select import SelectEntity
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
    discovery_info: DiscoveryInfoType | None = None,  # pylint: disable=unused-argument
) -> None:
    """Set up the sensor platform."""

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        IntConfigSelect(
            coordinator=coordinator,
            device_data=coordinator.data.get("entity_data", {}).get(device_id),
        )
        for device_id in coordinator.data.get("config_select_ids", [])
    )


class IntConfigSelect(IntBaseDevice, SelectEntity):  # type: ignore
    """Integration Number Entity."""

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

        self._select_options_map = {}
        if (
            self._config_option.get("option_type")
            == pyadcConfigurationOptionType.ADJUSTABLE_CHIME
        ):
            self._select_options_map = {
                member.name.title().replace("_", " "): member
                for member in pyadcCameraSkybellControllerExtension.ChimeAdjustableVolume
            }
        elif (
            self._config_option.get("option_type")
            == pyadcConfigurationOptionType.MOTION_SENSITIVITY
        ):
            self._select_options_map = {
                member.name.title().replace("_", " "): member
                for member in pyadcCameraSkybellControllerExtension.MotionSensitivity
            }
        else:
            log.error(
                "%s: Encountered unknown select configuration type when initializing %s.",
                __name__,
                self.unique_id,
            )

        self._attr_options: list = list(self._select_options_map.keys())

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
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if (
            self._config_option.get("option_type")
            == pyadcConfigurationOptionType.ADJUSTABLE_CHIME
        ):
            if (
                current_value := self._config_option.get("current_value")
            ) == pyadcCameraSkybellControllerExtension.ChimeAdjustableVolume.OFF:
                return "mdi:volume-mute"
            if (
                current_value
                == pyadcCameraSkybellControllerExtension.ChimeAdjustableVolume.LOW
            ):
                return "mdi:volume-low"
            if (
                current_value
                == pyadcCameraSkybellControllerExtension.ChimeAdjustableVolume.MEDIUM
            ):
                return "mdi:volume-medium"
            if (
                current_value
                == pyadcCameraSkybellControllerExtension.ChimeAdjustableVolume.HIGH
            ):
                return "mdi:volume-high"
        elif (
            self._config_option.get("option_type")
            == pyadcConfigurationOptionType.MOTION_SENSITIVITY
        ):
            return "mdi:tune"

        return super().icon if isinstance(super().icon, str) else None

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""

        if isinstance(current_value := self._config_option.get("current_value"), Enum):
            return current_value.name.title().replace("_", " ")

        return None

    @property
    def device_info(self) -> dict:
        """Return info to categorize this entity as a device."""

        # Associate with parent device.
        return {
            "identifiers": {(DOMAIN, self._device.get("parent_id"))},
        }

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        await self.async_change_setting_callback(
            self._config_option.get("slug"), self._select_options_map[option]
        )
