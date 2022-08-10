"""Base device."""
from __future__ import annotations

from enum import Enum
import logging
from typing import NamedTuple

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pyalarmdotcomajax.devices import BaseDevice as libBaseDevice
from pyalarmdotcomajax.extensions import ConfigurationOption as libConfigurationOption

from .alarmhub import AlarmHub
from .const import DOMAIN

log = logging.getLogger(__name__)


class SubdeviceMetadata(NamedTuple):
    """Metadata for subdevice types."""

    name: str
    suffix: str


class AttributeSubdevice(Enum):
    """Attribute-subdevice type enum."""

    DEBUG = SubdeviceMetadata("Debug", "debug")
    MALFUNCTION = SubdeviceMetadata("Malfunction", "malfunction")
    BATTERY = SubdeviceMetadata("Battery", "low_battery")


class BaseDevice(CoordinatorEntity):  # type: ignore
    """Base class for ADC entities."""

    _device_type_name: str = "Device"

    def __init__(
        self,
        alarmhub: AlarmHub,
        device: libBaseDevice,
        parent_id: str | None = None,
    ) -> None:
        """Initialize class."""
        super().__init__(alarmhub.coordinator)

        self._adc_id = device.id_
        self._device = device
        self._alarmhub = alarmhub
        self._attr_has_entity_name = True

        self.parent_id = parent_id

    @property
    def available(self) -> bool:
        """Return whether device is available."""

        if not self._device:
            log.error(
                "%s: No device data available for %s (%s).",
                __name__,
                self.name,
                self._adc_id,
            )
            return False

        if isinstance(self, ButtonEntity):
            return True

        if hasattr(self, "is_on"):
            return self.is_on is not None
        if hasattr(self, "state"):
            return self.state is not None
        if hasattr(self, "is_locked"):
            return self.is_locked is not None

        return True  # Covers switches, numbers, etc.

    @property
    def device_type_name(self) -> str:
        """Return human readable device type name."""

        return self._device_type_name

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        self.update_device_data()

    @callback  # type: ignore
    def _handle_coordinator_update(self) -> None:
        """Update the entity with new REST API data."""

        self._device = self._alarmhub.system.get_device_by_id(self._adc_id)

        if hasattr(self, "_attr_extra_state_attributes"):
            self._attr_extra_state_attributes.update(
                {
                    "raw_state_text": self._device.raw_state_text,
                }
            )

        self.update_device_data()
        self.async_write_ha_state()

    @callback  # type: ignore
    def update_device_data(self) -> None:
        """Update the entity when new data comes from the REST API."""
        raise NotImplementedError()

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


class HardwareBaseDevice(BaseDevice):
    """Base device for actual hardware: sensors, locks, control panels, etc."""

    def __init__(
        self,
        alarmhub: AlarmHub,
        device: libBaseDevice,
        parent_id: str | None = None,
    ) -> None:
        """Initialize class."""
        super().__init__(alarmhub, device, parent_id)

        log.debug(
            "%s: Initializing [%s: %s (%s)].",
            __name__,
            device.__class__.__name__.lower(),
            device.name,
            device.id_,
        )

        self._attr_unique_id = device.id_

        self._attr_extra_state_attributes = {
            "mac_address": self._device.mac_address,
            "raw_state_text": self._device.raw_state_text,
        }

        self._attr_device_info = {
            "default_manufacturer": "Alarm.com",
            "name": device.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "via_device": (DOMAIN, self.parent_id),
        }


class AttributeBaseDevice(BaseDevice):
    """Base device for attributes of real hardware: battery level, malfunction, debug, etc."""

    def __init__(
        self,
        alarmhub: AlarmHub,
        device: libBaseDevice,
        subdevice_type: AttributeSubdevice,
    ) -> None:
        """Initialize class."""
        super().__init__(alarmhub, device, device.id_)

        log.debug(
            "%s: Initializing [%s: %s (%s)] [Attribute: %s].",
            __name__,
            device.__class__.__name__.title(),
            device.name,
            device.id_,
            subdevice_type.name.title(),
        )

        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        self._attr_unique_id = f"{device.id_}_{subdevice_type.value.suffix}"

        self._attr_name = f"{subdevice_type.value.name}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._device.id_)},
        }


class ConfigBaseDevice(BaseDevice):
    """Base device for devices based on configuration options."""

    def __init__(
        self,
        alarmhub: AlarmHub,
        device: libBaseDevice,
        config_option: libConfigurationOption,
    ) -> None:
        """Initialize class."""
        super().__init__(alarmhub, device, device.id_)

        log.debug(
            "%s: Initializing [%s: %s (%s)] [Config Option: %s].",
            __name__,
            device.__class__.__name__.title(),
            device.name,
            device.id_,
            config_option.name.title(),
        )

        self._attr_entity_category = EntityCategory.CONFIG

        self._attr_unique_id = f"{device.id_}_{config_option.slug.replace('-','_')}"

        self._attr_name = f"{config_option.name}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._device.id_)},
        }

        self._config_option = config_option

        self._device = device
