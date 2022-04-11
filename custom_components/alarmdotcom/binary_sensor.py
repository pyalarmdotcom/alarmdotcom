"""Alarmdotcom implementation of an HA binary sensor."""
from __future__ import annotations

from enum import Enum
import logging
import re
from typing import Any

from homeassistant import core
from homeassistant.components.binary_sensor import BinarySensorDeviceClass as bsdc
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from pyalarmdotcomajax.entities import ADCSensor
from pyalarmdotcomajax.entities import ADCSensorSubtype

from . import ADCIEntity
from . import const as adci
from .controller import ADCIController
from .device_type_langs import LANG_DOOR
from .device_type_langs import LANG_WINDOW

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    controller: ADCIController = hass.data[adci.DOMAIN][config_entry.entry_id]

    # Create "real" Alarm.com sensors.
    async_add_entities(
        ADCIBinarySensor(controller, controller.devices.get("entity_data", {}).get(sensor_id))  # type: ignore
        for sensor_id in controller.devices.get("sensor_ids", [])
    )

    # Create "virtual" low battery sensors for Alarm.com sensors and locks.
    async_add_entities(
        ADCIBatterySensor(controller, controller.devices.get("entity_data", {}).get(battery_id))  # type: ignore
        for battery_id in controller.devices.get("low_battery_ids", [])
    )

    # Create "virtual" problem sensors for Alarm.com sensors and locks.
    async_add_entities(
        ADCIProblemSensor(controller, controller.devices.get("entity_data", {}).get(malfunction_id))  # type: ignore
        for malfunction_id in controller.devices.get("malfunction_ids", [])
    )


class ADCIBinarySensor(ADCIEntity, BinarySensorEntity):  # type: ignore
    """Binary sensor device class."""

    def __init__(self, controller: ADCIController, device_data: adci.ADCISensorData):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(controller, device_data)

        self._device_subtype_raw: Enum | None = self._device.get("device_subtype")
        self._device: adci.ADCISensorData = device_data

        log.debug(
            "%s: Initializing Alarm.com sensor entity for sensor %s.",
            __name__,
            self.unique_id,
        )

        # Try to determine whether contact sensor is for a window or door by matching strings.
        # Do this in __init__ because it's expensive.
        # We don't want to run this logic on every update.
        self._derived_class: bsdc = None
        if self._device_subtype_raw == ADCSensorSubtype.CONTACT_SENSOR:
            for _, word in LANG_DOOR:
                if (
                    re.search(
                        word,
                        device_data["name"],
                        re.IGNORECASE,
                    )
                    is not None
                ):
                    self._derived_class = bsdc.DOOR
            for _, word in LANG_WINDOW:
                if (
                    re.search(
                        word,
                        device_data["name"],
                        re.IGNORECASE,
                    )
                    is not None
                ):
                    self._derived_class = bsdc.WINDOW

    @property
    def device_class(self) -> bsdc:
        """Return type of binary sensor."""

        if (
            self._derived_class is not None
            and self._device_subtype_raw == ADCSensorSubtype.CONTACT_SENSOR
        ):
            return self._derived_class
        if self._device_subtype_raw == ADCSensorSubtype.SMOKE_DETECTOR:
            return bsdc.SMOKE
        if self._device_subtype_raw == ADCSensorSubtype.CO_DETECTOR:
            return bsdc.CO
        if self._device_subtype_raw == ADCSensorSubtype.PANIC_BUTTON:
            return bsdc.SAFETY
        if self._device_subtype_raw in [
            ADCSensorSubtype.GLASS_BREAK_DETECTOR,
            ADCSensorSubtype.PANEL_GLASS_BREAK_DETECTOR,
        ]:
            return bsdc.VIBRATION
        if self._device_subtype_raw in [
            ADCSensorSubtype.MOTION_SENSOR,
            ADCSensorSubtype.PANEL_MOTION_SENSOR,
        ]:
            return bsdc.MOTION
        if self._device_subtype_raw == ADCSensorSubtype.FREEZE_SENSOR:
            return bsdc.COLD

        return None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if self.device_class in [bsdc.SMOKE, bsdc.CO, bsdc.GAS]:
            if not self.available:
                return "mdi:smoke-detector-variant-off"
            if self.is_on:
                return "mdi:smoke-detector-variant-alert"
            return "mdi:smoke-detector-variant"
        if hasattr(self, "_attr_icon"):
            return self._attr_icon  # type: ignore
        if hasattr(self, "entity_description"):
            return self.entity_description.icon  # type: ignore
        return None

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""

        if self._device.get("state") in [
            ADCSensor.DeviceState.CLOSED,
            ADCSensor.DeviceState.IDLE,
            ADCSensor.DeviceState.DRY,
        ]:
            return False
        elif self._device.get("state") in [
            ADCSensor.DeviceState.OPEN,
            ADCSensor.DeviceState.ACTIVE,
            ADCSensor.DeviceState.WET,
        ]:
            return True

        return None


class ADCIBatterySensor(ADCIEntity, BinarySensorEntity):  # type: ignore
    """Returns low battery state for Alarm.com sensors and locks."""

    def __init__(self, controller: ADCIController, device_data: adci.ADCISensorData):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(controller, device_data)

        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_class = bsdc.BATTERY

    @property
    def device_info(self) -> dict[str, Any]:
        """Return info to categorize this entity as a device."""

        # Associate with parent device.
        return {
            "identifiers": {(adci.DOMAIN, self._device.get("parent_id"))},
        }

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""

        if self._device.get("state") in [True, False]:
            return bool(self._device.get("state"))

        return None


class ADCIProblemSensor(ADCIEntity, BinarySensorEntity):  # type: ignore
    """Returns malfunction state for Alarm.com sensors and locks."""

    def __init__(self, controller: ADCIController, device_data: adci.ADCISensorData):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(controller, device_data)

        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_class = bsdc.PROBLEM

    @property
    def device_info(self) -> dict[str, Any]:
        """Return info to categorize this entity as a device."""

        # Associate with parent device.
        return {
            "identifiers": {(adci.DOMAIN, self._device.get("parent_id"))},
        }

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""

        if self._device.get("state") in [True, False]:
            return bool(self._device.get("state"))

        return None
