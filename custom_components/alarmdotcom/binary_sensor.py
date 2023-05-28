"""Alarmdotcom implementation of an HA binary sensor."""
from __future__ import annotations

import logging
import re
from enum import Enum
from typing import cast

from homeassistant import core
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback, DiscoveryInfoType
from pyalarmdotcomajax.devices.registry import AllDevices_t
from pyalarmdotcomajax.devices.sensor import Sensor as libSensor
from pyalarmdotcomajax.devices.water_sensor import WaterSensor as libWaterSensor

from .base_device import AttributeBaseDevice, AttributeSubdevice, HardwareBaseDevice
from .const import DATA_CONTROLLER, DOMAIN, SENSOR_SUBTYPE_BLACKLIST
from .controller import AlarmIntegrationController
from .device_type_langs import LANG_DOOR, LANG_WINDOW

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,  # pylint: disable=unused-argument
) -> None:
    """Set up the sensor platform."""

    # Create "real" Alarm.com sensors.
    controller: AlarmIntegrationController = hass.data[DOMAIN][config_entry.entry_id][DATA_CONTROLLER]

    async_add_entities(
        BinarySensor(
            controller=controller,
            device=device,
        )
        for device in [*controller.api.devices.sensors.values(), *controller.api.devices.water_sensors.values()]
        if device.device_subtype not in SENSOR_SUBTYPE_BLACKLIST
    )

    # Create "virtual" low battery sensors.
    async_add_entities(
        BatteryAttributeSensor(
            controller=controller,
            device=device,
        )
        for device in controller.api.devices.all.values()
        if None not in [device.battery_low, device.battery_critical]
        and not (isinstance(device, libSensor) and device.device_subtype in SENSOR_SUBTYPE_BLACKLIST)
    )

    # Create "virtual" problem sensors for Alarm.com sensors and locks.
    async_add_entities(
        MalfunctionAttributeSensor(
            controller=controller,
            device=device,
        )
        for device in controller.api.devices.all.values()
        if device.malfunction is not None
        and not (isinstance(device, libSensor) and device.device_subtype in SENSOR_SUBTYPE_BLACKLIST)
    )


class BinarySensor(HardwareBaseDevice, BinarySensorEntity):  # type: ignore
    """Binary sensor device class."""

    _device: libSensor

    def __init__(self, controller: AlarmIntegrationController, device: AllDevices_t) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(controller, device, device.partition_id)

        self._attr_device_class = self._determine_device_class()

    @property
    def device_type_name(self) -> str:
        """Return human readable device type name based on device class."""

        device_class: BinarySensorDeviceClass | None = self._device.device_subtype

        try:
            return cast(str, BinarySensorDeviceClass[device_class].value).replace("_", " ").title()
        except AttributeError:
            return "Sensor"

    def _update_device_data(self) -> None:
        """Update the entity when coordinator is updated."""

        self._attr_is_on = self._determine_is_on(self._device.state)
        self._attr_icon = self._determine_icon(self._attr_is_on)

    #
    # Helpers
    #

    def _determine_is_on(self, state: Enum | None) -> bool | None:
        log.info(
            "Processing state %s for %s",
            state,
            self.name or self._device.name,
        )

        if state in [
            libSensor.DeviceState.CLOSED,
            libSensor.DeviceState.IDLE,
            libWaterSensor.DeviceState.DRY,
        ]:
            return False

        if state in [
            libSensor.DeviceState.OPEN,
            libSensor.DeviceState.ACTIVE,
            libWaterSensor.DeviceState.WET,
        ]:
            return True

        if state == libSensor.DeviceState.UNKNOWN:
            return None

        log.exception(
            "Cannot determine binary sensor state. Found raw state of %s.",
            state,
        )

        return None

    def _determine_icon(self, is_on: bool | None) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if self.device_class in [
            BinarySensorDeviceClass.SMOKE,
            BinarySensorDeviceClass.CO,
            BinarySensorDeviceClass.GAS,
        ]:
            if self.available and is_on:
                return "mdi:smoke-detector-variant-alert"

            if self.available and not is_on:
                return "mdi:smoke-detector-variant"

            return "mdi:smoke-detector-variant-off"

        return str(super().icon) if isinstance(super().icon, str) else None

    def _determine_device_class(self) -> BinarySensorDeviceClass:
        """Return type of binary sensor."""

        # Contact sensor:

        # Try to determine whether contact sensor is for a window or door by matching strings.
        derived_class: BinarySensorDeviceClass = None
        if (raw_subtype := self._device.device_subtype) in [
            libSensor.Subtype.CONTACT_SENSOR,
            libSensor.Subtype.CONTACT_SHOCK_SENSOR,
        ]:
            for _, word in LANG_DOOR:
                if (
                    re.search(
                        word,
                        str(self._device.name),
                        re.IGNORECASE,
                    )
                    is not None
                ):
                    derived_class = BinarySensorDeviceClass.DOOR
            for _, word in LANG_WINDOW:
                if (
                    re.search(
                        word,
                        str(self._device.name),
                        re.IGNORECASE,
                    )
                    is not None
                ):
                    derived_class = BinarySensorDeviceClass.WINDOW

        if derived_class is not None and raw_subtype in [
            libSensor.Subtype.CONTACT_SENSOR,
            libSensor.Subtype.CONTACT_SHOCK_SENSOR,
        ]:
            return derived_class

        # Water sensor:

        if isinstance(self._device, libWaterSensor):
            return BinarySensorDeviceClass.MOISTURE

        # All other sensors:

        if raw_subtype == libSensor.Subtype.SMOKE_DETECTOR:
            return BinarySensorDeviceClass.SMOKE
        if raw_subtype == libSensor.Subtype.CO_DETECTOR:
            return BinarySensorDeviceClass.CO
        if raw_subtype == libSensor.Subtype.PANIC_BUTTON:
            return BinarySensorDeviceClass.SAFETY
        if raw_subtype in [
            libSensor.Subtype.GLASS_BREAK_DETECTOR,
            libSensor.Subtype.PANEL_GLASS_BREAK_DETECTOR,
        ]:
            return BinarySensorDeviceClass.VIBRATION
        if raw_subtype in [
            libSensor.Subtype.MOTION_SENSOR,
            libSensor.Subtype.PANEL_MOTION_SENSOR,
        ]:
            return BinarySensorDeviceClass.MOTION
        if raw_subtype == libSensor.Subtype.FREEZE_SENSOR:
            return BinarySensorDeviceClass.COLD

        return None


class BatteryAttributeSensor(AttributeBaseDevice, BinarySensorEntity):  # type: ignore
    """Low battery sensor."""

    subdevice_type = AttributeSubdevice.BATTERY

    BATTERY_NORMAL = "Normal"
    BATTERY_LOW = "Low"
    BATTERY_CRITICAL = "Critical"

    def __init__(
        self,
        controller: AlarmIntegrationController,
        device: AllDevices_t,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(controller, device, self.subdevice_type)

        self._attr_device_class = BinarySensorDeviceClass.BATTERY

        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.id_)},
        }

        self._attr_extra_state_attributes = {"battery_level": self._determine_battery_level()}

    @callback
    def _update_device_data(self) -> None:
        """Update the entity when coordinator is updated."""

        self._attr_is_on = (battery_level := self._determine_battery_level()) != self.BATTERY_NORMAL

        self._attr_extra_state_attributes.update({"battery_level": battery_level})

    def _determine_battery_level(self) -> str:
        """Determine battery level attribute."""

        if self._device.battery_critical:
            return self.BATTERY_CRITICAL

        if self._device.battery_low:
            return self.BATTERY_LOW

        return self.BATTERY_NORMAL


class MalfunctionAttributeSensor(AttributeBaseDevice, BinarySensorEntity):  # type: ignore
    """Malfunction sensor."""

    subdevice_type = AttributeSubdevice.MALFUNCTION

    def __init__(
        self,
        controller: AlarmIntegrationController,
        device: AllDevices_t,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(controller, device, self.subdevice_type)

        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.id_)},
        }

    def _update_device_data(self) -> None:
        """Update the entity when coordinator is updated."""

        self._attr_is_on = self._device.malfunction
