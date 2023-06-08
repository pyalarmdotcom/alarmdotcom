"""Alarmdotcom implementation of an HA binary sensor."""
from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from homeassistant import core
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback, DiscoveryInfoType
from pyalarmdotcomajax.devices.registry import AllDevices_t
from pyalarmdotcomajax.devices.sensor import Sensor as libSensor
from pyalarmdotcomajax.devices.water_sensor import WaterSensor as libWaterSensor

from .base_device import AttributeBaseDevice, BaseDevice, HardwareBaseDevice
from .const import DATA_CONTROLLER, DOMAIN, SENSOR_SUBTYPE_BLACKLIST
from .controller import AlarmIntegrationController
from .device_type_langs import LANG_DOOR, LANG_WINDOW

LOGGER = logging.getLogger(__name__)


@dataclass
class AlarmdotcomAttributeDescriptionMixin:
    """Functions for an attribute entity."""

    value_fn: Callable[[BaseDevice], bool | None]
    filter_fn: Callable[[AllDevices_t], bool]
    extra_attribs_fn: Callable[[BaseDevice], dict | None]


@dataclass
class AlarmdotcomAttributeDescription(BinarySensorEntityDescription, AlarmdotcomAttributeDescriptionMixin):  # type: ignore
    """Describes an attribute entity."""


ATTRIBUTE_BINARY_SENSORS: Final = [
    AlarmdotcomAttributeDescription(
        key="malfunction",
        name="Malfunction",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        has_entity_name=True,
        extra_attribs_fn=lambda device: {},
        value_fn=lambda device: device.malfunction,
        filter_fn=lambda device: device.malfunction is not None,
    ),
    AlarmdotcomAttributeDescription(
        key="battery",
        name="Battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.BATTERY,
        has_entity_name=True,
        extra_attribs_fn=lambda device: {"battery_level": device.battery_level},
        value_fn=lambda device: device.battery_alert,
        filter_fn=lambda device: device.battery_critical is not None and device.battery_low is not None,
    ),
]


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
        if device.device_subtype not in SENSOR_SUBTYPE_BLACKLIST and device.has_state
    )

    # Create "virtual" low battery and malfunction sensors.

    async_add_entities(
        AttributeBinarySensor(
            controller=controller,
            device=device,
            description=description,
        )
        for description in ATTRIBUTE_BINARY_SENSORS
        for device in controller.api.devices.all.values()
        if (
            description.filter_fn(device)
            and not (isinstance(device, libSensor) and device.device_subtype in SENSOR_SUBTYPE_BLACKLIST)
            and device.has_state
        )
    )


class BinarySensor(HardwareBaseDevice, BinarySensorEntity):  # type: ignore
    """Binary sensor device class."""

    _device: libSensor

    def __init__(self, controller: AlarmIntegrationController, device: AllDevices_t) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(controller, device)

    @property
    def device_type_name(self) -> str:
        """Return human readable device type name based on device class."""

        return str(self.device_class.value.replace("_", " ").title()) if self.device_class else "Sensor"

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the class of this sensor, from DEVICE_CLASSES."""

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

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""

        # LOGGER.info(
        #     "Processing state %s for %s",
        #     self._device.state,
        #     self.name or self._device.name,
        # )

        match self._device.state:
            case libSensor.DeviceState.CLOSED | libSensor.DeviceState.IDLE | libWaterSensor.DeviceState.DRY:
                return False
            case libSensor.DeviceState.OPEN | libSensor.DeviceState.ACTIVE | libWaterSensor.DeviceState.WET:
                return True

        LOGGER.error("Cannot determine binary sensor state. Found raw state of %s.", self._device.state)
        return None


class AttributeBinarySensor(AttributeBaseDevice, BinarySensorEntity):  # type: ignore
    """Attribute binary sensor."""

    entity_description: AlarmdotcomAttributeDescription

    def __init__(
        self,
        controller: AlarmIntegrationController,
        device: AllDevices_t,
        description: AlarmdotcomAttributeDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""

        super().__init__(controller, device, description)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of the entity."""

        extra_attribs = {}.update(super().extra_state_attributes)

        if extra_attribs := self.entity_description.extra_attribs_fn(self):
            extra_attribs.update(extra_attribs)

        return extra_attribs

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""

        return self.entity_description.value_fn(self)
