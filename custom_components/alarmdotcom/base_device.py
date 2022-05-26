"""Base device."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any
from typing import TypedDict

from homeassistant.components import persistent_notification
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from pyalarmdotcomajax.extensions import (
    ConfigurationOption as pyadcConfigurationOption,
)
from typing_extensions import NotRequired

from .const import DOMAIN

log = logging.getLogger(__name__)


class IntBaseDevice(CoordinatorEntity):  # type: ignore
    """Base class for ADC entities."""

    class DataStructure(TypedDict):
        """Base dict for an ADCI entity."""

        unique_id: str
        name: str
        identifiers: NotRequired[list]
        battery_low: NotRequired[bool]
        malfunction: NotRequired[bool]
        mac_address: NotRequired[str]
        debug_data: NotRequired[str]
        model: NotRequired[str]
        manufacturer: NotRequired[str]

    _device_type_name: str = "Device"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_data: Any,
    ) -> None:
        """Initialize class."""
        super().__init__(coordinator)
        self._device = device_data
        self.coordinator = coordinator

        self._attr_unique_id = device_data["unique_id"]
        self._attr_name = device_data["name"]

        try:
            self.coordinator.data
        except KeyError:
            log.error("Failed to initialize control functions for %s.", self.unique_id)
            self._attr_available = False

    @property
    def device_type_name(self) -> str:
        """Return human readable device type name."""

        return self._device_type_name

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return entity specific state attributes."""

        return {
            "mac_address": self._device.get("mac_address"),
            "raw_state_text": self._device.get("raw_state_text"),
        }

    @property
    def device_info(self) -> dict:
        """Return the device information."""

        return {
            "default_manufacturer": "Alarm.com",
            "name": self.name,
            "identifiers": {(DOMAIN, self._device.get("unique_id"))},
            "via_device": (DOMAIN, self._device.get("parent_id")),
        }

    @callback  # type: ignore
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._device = self.coordinator.data["entity_data"][self.unique_id]
            self.async_write_ha_state()
        except KeyError as err:
            log.debug(self.coordinator.data)
            log.error(
                "%s: Device database update failed for %s.", __name__, self._device
            )
            raise UpdateFailed from err

    def _show_permission_error(self, action: str = "") -> None:
        """Show Home Assistant notification to alert user that they lack permission to perform action."""

        error_msg = (
            "Your Alarm.com user does not have permission to"
            f" {action} the {self.device_type_name.lower()}, {self.name}. Please log"
            " in to Alarm.com to grant the appropriate permissions to your"
            " account."
        )
        persistent_notification.async_create(
            self.hass,
            error_msg,
            title="Alarm.com Error",
            notification_id="alarmcom_permission_error",
        )


class IntSystemDataStructure(IntBaseDevice.DataStructure):
    """Dict for an ADCI system."""

    unit_id: str


class IntConfigOnlyDeviceDataStructure(IntBaseDevice.DataStructure):
    """Dict for an ADCI configuration-only device."""

    parent_id: str


class IntConfigEntityDataStructure(TypedDict):
    """Configuration entity data structure."""

    unique_id: str
    parent_id: str
    name: str
    config_option: pyadcConfigurationOption
    async_change_setting_callback: Callable
