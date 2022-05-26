"""Alarmdotcom implementation of an HA binary sensor."""
from __future__ import annotations

from enum import Enum
import logging
import re
from typing import Any
from typing import cast

from homeassistant import core
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyalarmdotcomajax.devices import Sensor as pyadcSensor
from typing_extensions import NotRequired

from .base_device import IntBaseDevice
from .const import DOMAIN
from .device_type_langs import LANG_DOOR
from .device_type_langs import LANG_WINDOW

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,  # pylint: disable=unused-argument
) -> None:
    """Set up the sensor platform."""

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create "real" Alarm.com sensors.
    async_add_entities(
        IntBinarySensor(
            coordinator=coordinator,
            device_data=coordinator.data.get("entity_data", {}).get(device_id),
        )
        for device_id in coordinator.data.get("sensor_ids", [])
    )

    # Create "virtual" low battery sensors for Alarm.com sensors and locks.
    async_add_entities(
        IntBatterySensor(
            coordinator=coordinator,
            device_data=coordinator.data.get("entity_data", {}).get(device_id),
        )
        for device_id in coordinator.data.get("low_battery_ids", [])
    )

    # Create "virtual" problem sensors for Alarm.com sensors and locks.
    async_add_entities(
        IntProblemSensor(
            coordinator=coordinator,
            device_data=coordinator.data.get("entity_data", {}).get(device_id),
        )
        for device_id in coordinator.data.get("malfunction_ids", [])
    )


class IntBinarySensor(IntBaseDevice, BinarySensorEntity):  # type: ignore
    """Binary sensor device class."""

    class DataStructure(IntBaseDevice.DataStructure):
        """Dict for an ADCI sensor."""

        device_subtype: NotRequired[Enum]
        partition_id: NotRequired[str]
        raw_state_text: NotRequired[str]
        state: pyadcSensor.DeviceState
        parent_id: str

    def __init__(
        self, coordinator: DataUpdateCoordinator, device_data: DataStructure
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, device_data)

        self._device_subtype_raw: Enum | None = self._device.get("device_subtype")
        self._device: IntBinarySensor.DataStructure = device_data

        log.debug(
            "%s: Initializing Alarm.com sensor entity for sensor %s.",
            __name__,
            self.unique_id,
        )

        # Try to determine whether contact sensor is for a window or door by matching strings.
        # Do this in __init__ because it's expensive.
        # We don't want to run this logic on every update.
        self._derived_class: BinarySensorDeviceClass = None
        if self._device_subtype_raw == pyadcSensor.Subtype.CONTACT_SENSOR:
            for _, word in LANG_DOOR:
                if (
                    re.search(
                        word,
                        device_data["name"],
                        re.IGNORECASE,
                    )
                    is not None
                ):
                    self._derived_class = BinarySensorDeviceClass.DOOR
            for _, word in LANG_WINDOW:
                if (
                    re.search(
                        word,
                        device_data["name"],
                        re.IGNORECASE,
                    )
                    is not None
                ):
                    self._derived_class = BinarySensorDeviceClass.WINDOW

    @property
    def device_type_name(self) -> str:
        """Return human readable device type name based on device class."""

        device_class: BinarySensorDeviceClass | None = self._device.get("device_class")

        try:
            return (
                cast(str, BinarySensorDeviceClass[device_class].value)
                .replace("_", " ")
                .title()
            )
        except AttributeError:
            return "Sensor"

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return type of binary sensor."""

        if (
            self._derived_class is not None
            and self._device_subtype_raw == pyadcSensor.Subtype.CONTACT_SENSOR
        ):
            return self._derived_class
        if self._device_subtype_raw == pyadcSensor.Subtype.SMOKE_DETECTOR:
            return BinarySensorDeviceClass.SMOKE
        if self._device_subtype_raw == pyadcSensor.Subtype.CO_DETECTOR:
            return BinarySensorDeviceClass.CO
        if self._device_subtype_raw == pyadcSensor.Subtype.PANIC_BUTTON:
            return BinarySensorDeviceClass.SAFETY
        if self._device_subtype_raw in [
            pyadcSensor.Subtype.GLASS_BREAK_DETECTOR,
            pyadcSensor.Subtype.PANEL_GLASS_BREAK_DETECTOR,
        ]:
            return BinarySensorDeviceClass.VIBRATION
        if self._device_subtype_raw in [
            pyadcSensor.Subtype.MOTION_SENSOR,
            pyadcSensor.Subtype.PANEL_MOTION_SENSOR,
        ]:
            return BinarySensorDeviceClass.MOTION
        if self._device_subtype_raw == pyadcSensor.Subtype.FREEZE_SENSOR:
            return BinarySensorDeviceClass.COLD

        return None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if self.device_class in [
            BinarySensorDeviceClass.SMOKE,
            BinarySensorDeviceClass.CO,
            BinarySensorDeviceClass.GAS,
        ]:
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
            pyadcSensor.DeviceState.CLOSED,
            pyadcSensor.DeviceState.IDLE,
            pyadcSensor.DeviceState.DRY,
        ]:
            return False

        if self._device.get("state") in [
            pyadcSensor.DeviceState.OPEN,
            pyadcSensor.DeviceState.ACTIVE,
            pyadcSensor.DeviceState.WET,
        ]:
            return True

        return None


class IntBatterySensor(IntBaseDevice, BinarySensorEntity):  # type: ignore
    """Returns low battery state for Alarm.com sensors and locks."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_data: IntBinarySensor.DataStructure,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, device_data)

        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_class = BinarySensorDeviceClass.BATTERY

    @property
    def device_info(self) -> dict[str, Any]:
        """Return info to categorize this entity as a device."""

        # Associate with parent device.
        return {
            "identifiers": {(DOMAIN, self._device.get("parent_id"))},
        }

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""

        if self._device.get("state") in [True, False]:
            return bool(self._device.get("state"))

        return None


class IntProblemSensor(IntBaseDevice, BinarySensorEntity):  # type: ignore
    """Returns malfunction state for Alarm.com sensors and locks."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_data: IntBinarySensor.DataStructure,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, device_data)

        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def device_info(self) -> dict[str, Any]:
        """Return info to categorize this entity as a device."""

        # Associate with parent device.
        return {
            "identifiers": {(DOMAIN, self._device.get("parent_id"))},
        }

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""

        if self._device.get("state") in [True, False]:
            return bool(self._device.get("state"))

        return None
