"""Interfaces with Alarm.com binary sensors."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic

import pyalarmdotcomajax as pyadc
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .binary_sensor_words import LANG_DOOR, LANG_WINDOW
from .const import DATA_HUB, DOMAIN
from .entity import (
    AdcControllerT,
    AdcEntity,
    AdcEntityDescription,
    AdcManagedDeviceT,
)
from .util import cleanup_orphaned_entities_and_devices

if TYPE_CHECKING:
    from .hub import AlarmHub

log = logging.getLogger(__name__)

SENSOR_SUBTYPE_BLACKLIST = [
    pyadc.sensor.SensorSubtype.MOBILE_PHONE,  # Doesn't report anything useful.
    pyadc.sensor.SensorSubtype.SIREN,  # Doesn't report anything useful.
    pyadc.sensor.SensorSubtype.PANEL_IMAGE_SENSOR,  # No support yet
    pyadc.sensor.SensorSubtype.FIXED_PANIC,  # No support yet
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the binary sensor platform."""

    hub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id][DATA_HUB]

    entities: list[AdcBinarySensorEntity] = []
    for entity_description in ENTITY_DESCRIPTIONS:
        entities.extend(
            AdcBinarySensorEntity(
                hub=hub, resource_id=device.id, description=entity_description
            )
            for device in hub.api.managed_devices.values()
            if entity_description.supported_fn(hub, device.id)
        )

    async_add_entities(entities)

    current_entity_ids = {entity.entity_id for entity in entities}
    current_unique_ids = {
        uid for uid in (entity.unique_id for entity in entities) if uid is not None
    }
    await cleanup_orphaned_entities_and_devices(
        hass, config_entry, current_entity_ids, current_unique_ids, "binary_sensor"
    )


#
# MALFUNCTION SENSOR
#
@callback
def malfunction_is_on_fn(hub: AlarmHub, resource_id: str) -> bool:
    """Return the state of the binary sensor."""

    resource = hub.api.managed_devices.get(resource_id)

    if resource is None:
        return False

    return resource.attributes.is_malfunctioning


@callback
def malfunction_supported_fn(hub: AlarmHub, resource_id: str) -> bool:
    """Check if the binary sensor is supported."""

    resource = hub.api.managed_devices.get(resource_id)

    if resource is None:
        return False

    return (
        hasattr(resource.attributes, "is_malfunctioning")
        and getattr(resource.attributes, "device_type", None)
        not in SENSOR_SUBTYPE_BLACKLIST
    )


#
# ALARM BINARY SENSORS
#
@callback
def supported_fn(hub: AlarmHub, resource_id: str) -> bool:
    """Check if the binary sensor is supported."""

    resource = hub.api.sensors.get(resource_id) or hub.api.water_sensors.get(
        resource_id
    )

    if resource is None:
        return False

    return resource.attributes.device_type not in SENSOR_SUBTYPE_BLACKLIST


@callback
def is_on_fn(hub: AlarmHub, sensor_id: str) -> bool:
    """Return the state of the binary sensor."""

    resource = hub.api.sensors.get(sensor_id) or hub.api.water_sensors.get(sensor_id)

    if resource is None:
        return False

    return (resource.attributes.state.value % 2) == 0


@callback
def device_class_fn(hub: AlarmHub, sensor_id: str) -> BinarySensorDeviceClass | None:
    """Return the device class for the binary sensor."""

    resource = hub.api.sensors.get(sensor_id) or hub.api.water_sensors.get(sensor_id)

    if resource is None:
        return None

    #
    # Contact Sensor
    #

    # Try to determine whether contact sensor is for a window or door by matching strings.
    if (raw_subtype := resource.attributes.device_type) in [
        pyadc.sensor.SensorSubtype.CONTACT_SENSOR,
    ]:
        # Check if the sensor name matches any door or window keywords.
        # fmt: off
        if any(re.search(word, str(resource.name), re.IGNORECASE) for _, word in LANG_DOOR):
            return BinarySensorDeviceClass.DOOR
        if any(re.search(word, str(resource.name), re.IGNORECASE) for _, word in LANG_WINDOW):
            return BinarySensorDeviceClass.WINDOW
        # fmt: on

    #
    # Water Sensor
    #

    if isinstance(resource, pyadc.water_sensor.WaterSensor):
        return BinarySensorDeviceClass.MOISTURE

    #
    # All Other Sensors
    #

    # Mapping of SensorSubtype to BinarySensorDeviceClass for remaining types
    subtype_to_device_class = {
        pyadc.sensor.SensorSubtype.SMOKE_DETECTOR: BinarySensorDeviceClass.SMOKE,
        pyadc.sensor.SensorSubtype.CO_DETECTOR: BinarySensorDeviceClass.CO,
        pyadc.sensor.SensorSubtype.PANIC_BUTTON: BinarySensorDeviceClass.SAFETY,
        pyadc.sensor.SensorSubtype.GLASS_BREAK_DETECTOR: BinarySensorDeviceClass.VIBRATION,
        pyadc.sensor.SensorSubtype.PANEL_GLASS_BREAK_DETECTOR: BinarySensorDeviceClass.VIBRATION,
        pyadc.sensor.SensorSubtype.MOTION_SENSOR: BinarySensorDeviceClass.MOTION,
        pyadc.sensor.SensorSubtype.PANEL_MOTION_SENSOR: BinarySensorDeviceClass.MOTION,
        pyadc.sensor.SensorSubtype.FIXED_PANIC: BinarySensorDeviceClass.SAFETY,
        pyadc.sensor.SensorSubtype.FREEZE_SENSOR: BinarySensorDeviceClass.COLD,
        pyadc.sensor.SensorSubtype.CONTACT_SHOCK_SENSOR: BinarySensorDeviceClass.VIBRATION,
        # pyadc.sensor.SensorSubtype.SIREN: BinarySensorDeviceClass.SOUND,
        # pyadc.sensor.SensorSubtype.PANEL_IMAGE_SENSOR: BinarySensorDeviceClass.MOTION,
    }

    if raw_subtype in subtype_to_device_class:
        return subtype_to_device_class[raw_subtype]

    return None


@dataclass(frozen=True, kw_only=True)
class AdcBinarySensorEntityDescription(
    Generic[AdcManagedDeviceT, AdcControllerT],
    AdcEntityDescription[AdcManagedDeviceT, AdcControllerT],
    BinarySensorEntityDescription,
):
    """Base Alarm.com binary sensor entity description."""

    is_on_fn: Callable[[AlarmHub, str], bool]
    """Return whether the binary sensor is on."""
    device_class_fn: Callable[[AlarmHub, str], BinarySensorDeviceClass | None]
    """Return the device class for the binary sensor."""


ENTITY_DESCRIPTIONS: list[AdcEntityDescription] = [
    AdcBinarySensorEntityDescription[pyadc.sensor.Sensor, pyadc.SensorController](
        key="sensor",
        controller_fn=lambda hub, _: hub.api.sensors,
        is_on_fn=is_on_fn,
        device_class_fn=device_class_fn,
        supported_fn=supported_fn,
    ),
    AdcBinarySensorEntityDescription[
        pyadc.base.AdcDeviceResource, pyadc.BaseController
    ](
        key="malfunction",
        controller_fn=lambda hub, resource_id: hub.api.get_controller(resource_id),
        name="Malfunction",
        supported_fn=malfunction_supported_fn,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class_fn=lambda hub, resource_id: BinarySensorDeviceClass.PROBLEM,
        has_entity_name=False,
        is_on_fn=malfunction_is_on_fn,
    ),
]


class AdcBinarySensorEntity(
    AdcEntity[AdcManagedDeviceT, AdcControllerT], BinarySensorEntity
):
    """Base Alarm.com binary sensor entity."""

    entity_description: AdcBinarySensorEntityDescription

    @callback
    def initiate_state(self) -> None:
        """Initiate entity state."""

        self._attr_is_on = self.entity_description.is_on_fn(self.hub, self.resource_id)
        self._attr_device_class = self.entity_description.device_class_fn(
            self.hub, self.resource_id
        )

        super().initiate_state()

    @callback
    def update_state(self, message: pyadc.EventBrokerMessage | None = None) -> None:
        """Update entity state."""

        if isinstance(message, pyadc.ResourceEventMessage):
            self._attr_is_on = self.entity_description.is_on_fn(
                self.hub, self.resource_id
            )
