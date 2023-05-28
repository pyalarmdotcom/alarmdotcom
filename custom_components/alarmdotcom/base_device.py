"""Base device."""
from __future__ import annotations

import logging
from abc import abstractmethod
from collections.abc import MutableMapping
from enum import Enum
from typing import Any, NamedTuple

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from pyalarmdotcomajax.devices.registry import AllDevices_t
from pyalarmdotcomajax.extensions import ConfigurationOption as libConfigurationOption

from .const import DOMAIN
from .controller import AlarmIntegrationController

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
        controller: AlarmIntegrationController,
        device: AllDevices_t,
        parent_id: str | None = None,
    ) -> None:
        """Initialize class."""
        super().__init__(controller.update_coordinator)

        self._adc_id = device.id_
        self._device = device
        self._controller = controller
        self._attr_has_entity_name = True

        self.parent_id = parent_id

        self._attr_extra_state_attributes: MutableMapping[str, Any] = {}

    @property
    def available(self) -> bool:
        """Return whether device is available."""

        if not self._device:
            log.exception(
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

        self._device.register_external_update_callback(self._handle_coordinator_update)

        self._data_refresh_postprocessing()

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""

        await super().async_will_remove_from_hass()

        self._device.unregister_external_update_callback(self._handle_coordinator_update)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the entity with new cordinator-fetched data."""

        self._device = self._controller.api.devices.get(self._adc_id)

        self._data_refresh_postprocessing()

        self.async_write_ha_state()

    def _data_refresh_postprocessing(self) -> None:
        self._attr_extra_state_attributes.update(
            {
                "raw_state_text": self._device.raw_state_text,
            }
        )

        self._update_device_data()

    @abstractmethod
    def _update_device_data(self) -> None:
        """Device-type specific update processes to run when new device data is available."""
        raise NotImplementedError()

    def _show_permission_error(self, action: str = "") -> None:
        """Show Home Assistant notification.

        Alerts user that they lack permission to perform action.
        """

        # TODO: Convert to Home Assistant Repair item.

        error_msg = (
            f"Your Alarm.com user does not have permission to {action} the"
            f" {self.device_type_name.lower()}, {self._device.name} ({self._adc_id})."
            " Please log in to Alarm.com to grant the appropriate permissions to your"
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
        controller: AlarmIntegrationController,
        device: AllDevices_t,
        parent_id: str | None = None,
    ) -> None:
        """Initialize class."""
        super().__init__(controller, device, parent_id)

        log.info(
            "%s: Initializing [%s: %s (%s)].",
            __name__,
            device.__class__.__name__.lower(),
            device.name,
            device.id_,
        )

        self._attr_unique_id = device.id_

        self._attr_extra_state_attributes = {
            "raw_state_text": self._device.raw_state_text,
        }

        if mac_address := self._device.mac_address:
            self._attr_extra_state_attributes["mac_address"] = mac_address

        self._attr_device_info = {
            "default_manufacturer": "Alarm.com",
            "name": device.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "via_device": (DOMAIN, self.parent_id),
        }


class AttributeBaseDevice(BaseDevice):
    """Base device for attributes of real hardware.

    Includes battery level, malfunction, debug, etc.
    """

    def __init__(
        self,
        controller: AlarmIntegrationController,
        device: AllDevices_t,
        subdevice_type: AttributeSubdevice,
    ) -> None:
        """Initialize class."""
        super().__init__(controller, device, device.id_)

        log.info(
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
        controller: AlarmIntegrationController,
        device: AllDevices_t,
        config_option: libConfigurationOption,
    ) -> None:
        """Initialize class."""
        super().__init__(controller, device, device.id_)

        log.info(
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
