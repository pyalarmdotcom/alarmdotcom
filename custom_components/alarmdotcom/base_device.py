"""Base device."""
from __future__ import annotations

import contextlib
import logging
from collections.abc import Mapping, MutableMapping
from typing import Any, Final

from homeassistant.components import persistent_notification
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from pyalarmdotcomajax.devices.registry import AllDevices_t
from pyalarmdotcomajax.extensions import ConfigurationOption as libConfigurationOption

from . import const as c
from .const import (
    ATTRIB_BATTERY_CRITICAL,
    ATTRIB_BATTERY_LOW,
    ATTRIB_BATTERY_NORMAL,
    DEVICE_STATIC_ATTRIBUTES,
    DOMAIN,
)
from .controller import AlarmIntegrationController

LOGGER = logging.getLogger(__name__)


class BaseDevice(CoordinatorEntity):  # type: ignore
    """Base class for ADC entities."""

    _device_type_name = "Device"
    _attr_has_entity_name = True

    def __init__(
        self,
        controller: AlarmIntegrationController,
        device: AllDevices_t,
    ) -> None:
        """Initialize class."""
        super().__init__(controller.update_coordinator)

        self._adc_id: Final[str] = device.id_

        self._device = device

        self._controller = controller

        self._attr_extra_state_attributes: MutableMapping[str, Any] = {}

        self._attr_device_info = DeviceInfo(
            {
                "manufacturer": "Alarm.com",
                "name": device.name,
                "identifiers": {(DOMAIN, self._adc_id)},
                "via_device": (DOMAIN, self._device.partition_id),
            }
        )

    @property
    def device_type_name(self) -> str:
        """Return human readable device type name."""

        return self._device_type_name

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        self._device.register_external_update_callback(self._update_device_data)

        self._update_device_data()

        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""

        # This will fail for devices that were removed from ADC during this session.
        with contextlib.suppress(ValueError):
            self._device.unregister_external_update_callback(self._update_device_data)

        await super().async_will_remove_from_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the entity with new cordinator-fetched data."""

        super()._handle_coordinator_update()

        self._update_device_data()

    def _update_device_data(self) -> None:
        """Device-type specific update processes to run when new device data is available."""

        self._device = self._controller.api.devices.get(self._adc_id)

        self._legacy_refresh_attributes()

        self.async_write_ha_state()

        # LOGGER.debug("************** START DEVICE UPDATE *****************")
        LOGGER.info(
            f"Updated {self.device_type_name} {self._friendly_name_internal()} ({self._adc_id}): {self.state}"
        )
        # LOGGER.debug(json.dumps(self._device.raw_attributes, indent=4, sort_keys=True))
        # LOGGER.debug("************** END DEVICE UPDATE *****************")

    def _legacy_refresh_attributes(self) -> None:
        """Update HA when device is updated. Should be overridden by subclasses."""

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

    @property
    def battery_level(self) -> str | None:
        """Determine battery level attribute."""

        if self._device.battery_critical is None and self._device.battery_low is None:
            return None

        if self._device.battery_critical:
            return ATTRIB_BATTERY_CRITICAL

        if self._device.battery_low:
            return ATTRIB_BATTERY_LOW

        return ATTRIB_BATTERY_NORMAL

    @property
    def battery_alert(self) -> bool | None:
        """Determine battery alert attribute."""

        match self.battery_level:
            case c.ATTRIB_BATTERY_NORMAL:
                return False
            case c.ATTRIB_BATTERY_LOW | c.ATTRIB_BATTERY_CRITICAL:
                return True

        return None

    @property
    def malfunction(self) -> bool | None:
        """Determine malfunction attribute."""

        return bool(self._device.malfunction) if self._device.malfunction is not None else None


class HardwareBaseDevice(BaseDevice):
    """Base device for actual hardware: sensors, locks, control panels, etc."""

    def __init__(
        self,
        controller: AlarmIntegrationController,
        device: AllDevices_t,
    ) -> None:
        """Initialize class."""

        LOGGER.info(
            "%s: Initializing [%s: %s (%s)].",
            __name__,
            device.__class__.__name__.lower(),
            device.name,
            device.id_,
        )

        self._attr_unique_id = device.id_

        self._attr_name = device.name

        super().__init__(controller, device)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the client state attributes."""

        raw = self._controller.api.devices.get(self._adc_id).raw_attributes

        return {k: raw[k] for k in DEVICE_STATIC_ATTRIBUTES if k in raw}


class AttributeBaseDevice(BaseDevice):
    """Base device for attributes of real hardware.

    Includes battery level, malfunction, debug, etc.
    """

    def __init__(
        self,
        controller: AlarmIntegrationController,
        device: AllDevices_t,
        description: EntityDescription,
    ) -> None:
        """Initialize class."""

        LOGGER.info(
            "%s: Initializing [%s: %s (%s)] [Attribute: %s].",
            __name__,
            device.__class__.__name__.title(),
            device.name,
            device.id_,
            description.key.title(),
        )

        self.entity_description = description

        self._attr_unique_id = f"{device.id_}_{description.key}"

        super().__init__(controller, device)


class ConfigBaseDevice(BaseDevice):
    """Base device for devices based on configuration options."""

    def __init__(
        self,
        controller: AlarmIntegrationController,
        device: AllDevices_t,
        config_option: libConfigurationOption,
    ) -> None:
        """Initialize class."""

        LOGGER.info(
            "%s: Initializing [%s: %s (%s)] [Config Option: %s].",
            __name__,
            device.__class__.__name__.title(),
            device.name,
            device.id_,
            config_option.name.title(),
        )

        self._attr_unique_id = f"{device.id_}_{config_option.slug.replace('-','_')}"

        super().__init__(controller, device)

        self._attr_entity_category = EntityCategory.CONFIG

        self._attr_name = f"{config_option.name}"

        self._config_option = config_option
