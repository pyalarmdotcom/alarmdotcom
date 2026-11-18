"""Interfaces with Alarm.com binary sensors."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic

import _pyalarmdotcomajax as pyadc
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .binary_sensor_words import LANG_DOOR, LANG_WINDOW
from .camera_detection import CameraDetectionSensor, log_camera_detection
from .const import DOMAIN
from .entity import (
    AdcControllerT,
    AdcEntity,
    AdcEntityDescription,
    AdcManagedDeviceT,
)
from .util import cleanup_orphaned_entities_and_devices

if TYPE_CHECKING:
    from .hub import AlarmHub

# Entities are updated via push (websocket events), not per-entity polling -
# PARALLEL_UPDATES has no effect on update frequency here, but setting it
# to 0 is still the correct, explicit signal for a push-based integration.
PARALLEL_UPDATES = 0

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

    hub: AlarmHub = config_entry.runtime_data.hub

    entities: list[BinarySensorEntity] = []
    for entity_description in ENTITY_DESCRIPTIONS:
        entities.extend(
            AdcBinarySensorEntity(hub=hub, resource_id=device.id, description=entity_description)
            for device in hub.api.managed_devices.values()
            if entity_description.supported_fn(hub, device.id)
        )

    if getattr(hub.api.auth_controller, "has_trouble_conditions_service", False):
        active_system = hub.api.active_system
        entities.extend(
            TroubleConditionBinarySensorEntity(
                hub=hub,
                resource_id=active_system.id,
                trouble_type=trouble_type,
                name=name,
            )
            for trouble_type, name in SYSTEM_TROUBLE_SENSORS
        )
        entities.extend(
            DeviceTroubleBinarySensorEntity(hub=hub, resource_id=device.id)
            for device in hub.api.managed_devices.values()
        )

    camera_ids = {camera.id for camera in hub.api.cameras}
    if (session := config_entry.runtime_data.camera_session) is not None:
        try:
            camera_ids.update(str(camera["id"]) for camera in await session.get_camera_list())
        except Exception:
            # Video account permissions must never prevent security sensors loading.
            log.debug("Camera analytics discovery unavailable; security sensors continue.")
    entities.extend(
        CameraDetectionSensor(hub, resource_id, classification)
        for resource_id in sorted(camera_ids)
        for classification in ("person", "vehicle", "animal", "package")
    )
    if camera_ids:
        config_entry.async_on_unload(hub.api.events.subscribe(
            pyadc.EventBrokerTopic.DEVICE_ACTIVITY, log_camera_detection, ids=sorted(camera_ids),
        ))
    async_add_entities(entities)

    current_entity_ids = {entity.entity_id for entity in entities}
    current_unique_ids = {uid for uid in (entity.unique_id for entity in entities) if uid is not None}
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
        and getattr(resource.attributes, "device_type", None) not in SENSOR_SUBTYPE_BLACKLIST
    )

#
# ALARM BINARY SENSORS
#
@callback
def supported_fn(hub: AlarmHub, resource_id: str) -> bool:
    """Check if the binary sensor is supported."""

    resource = hub.api.sensors.get(resource_id) or hub.api.water_sensors.get(resource_id)

    if resource is None:
        return False

    return resource.attributes.device_type not in SENSOR_SUBTYPE_BLACKLIST

@callback
def is_on_fn(hub: AlarmHub, sensor_id: str) -> bool:
    """Return the state of the binary sensor."""

    resource = hub.api.sensors.get(sensor_id) or hub.api.water_sensors.get(sensor_id)

    if resource is None or resource.attributes.state == pyadc.sensor.SensorState.UNKNOWN:
        return False

    # Glass-break detectors may retain a stale activated state after restoration.
    # The explicit normal status reported by the panel takes precedence.
    if resource.attributes.device_type in (
        pyadc.sensor.SensorSubtype.GLASS_BREAK_DETECTOR,
        pyadc.sensor.SensorSubtype.PANEL_GLASS_BREAK_DETECTOR,
    ) and resource.attributes.open_closed_status == 3:
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
        pyadc.sensor.SensorSubtype.GLASS_BREAK_DETECTOR: BinarySensorDeviceClass.GLASS_BREAK,
        pyadc.sensor.SensorSubtype.PANEL_GLASS_BREAK_DETECTOR: BinarySensorDeviceClass.GLASS_BREAK,
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

#
# BYPASSED SENSOR
#
@callback
def bypassed_is_on_fn(hub: AlarmHub, resource_id: str) -> bool:
    """Return whether the sensor is bypassed."""

    resource = hub.api.sensors.get(resource_id)
    if resource is None:
        return False

    return bool(resource.attributes.is_bypassed)

@callback
def bypassed_supported_fn(hub: AlarmHub, resource_id: str) -> bool:
    """Check if the sensor bypass entity is supported."""

    resource = hub.api.sensors.get(resource_id)
    if resource is None:
        return False

    if resource.attributes.device_type in SENSOR_SUBTYPE_BLACKLIST:
        return False

    return bool(resource.attributes.supports_bypass or resource.attributes.supports_immediate_bypass)

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

@callback
def sensor_extra_attrib_fn(device: pyadc.base.AdcDeviceResource) -> dict[str, str]:
    """
    Expose the Alarm.com resource ID as an entity attribute.

    This is the identifier required by the alarmdotcom.bypass_sensor /
    alarmdotcom.unbypass_sensor services. Without this, finding it requires a
    Developer Tools -> Template lookup against the device's `identifiers`
    (see #14) -- surfacing it directly on the entity avoids that step.
    """

    return {"resource_id": device.id}

ENTITY_DESCRIPTIONS: list[AdcEntityDescription] = [
    AdcBinarySensorEntityDescription[pyadc.sensor.Sensor, pyadc.SensorController](
        key="sensor",
        controller_fn=lambda hub, _: hub.api.sensors,
        is_on_fn=is_on_fn,
        device_class_fn=device_class_fn,
        supported_fn=supported_fn,
        extra_attrib_fn=sensor_extra_attrib_fn,
    ),
    AdcBinarySensorEntityDescription[pyadc.sensor.Sensor, pyadc.SensorController](
        key="is_bypassed",
        controller_fn=lambda hub, _: hub.api.sensors,
        name="Bypassed",
        supported_fn=bypassed_supported_fn,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class_fn=lambda hub, resource_id: None,
        is_on_fn=bypassed_is_on_fn,
        extra_attrib_fn=sensor_extra_attrib_fn,
    ),
    AdcBinarySensorEntityDescription[pyadc.base.AdcDeviceResource, pyadc.BaseController](
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

class AdcBinarySensorEntity(AdcEntity[AdcManagedDeviceT, AdcControllerT], BinarySensorEntity):
    """Base Alarm.com binary sensor entity."""

    entity_description: AdcBinarySensorEntityDescription

    @callback
    def initiate_state(self) -> None:
        """Initiate entity state."""

        self._attr_is_on = self.entity_description.is_on_fn(self.hub, self.resource_id)
        self._attr_device_class = self.entity_description.device_class_fn(self.hub, self.resource_id)

        super().initiate_state()

    @callback
    def update_state(self, message: pyadc.EventBrokerMessage | None = None) -> None:
        """Update entity state."""

        if isinstance(message, pyadc.ResourceEventMessage):
            self._attr_is_on = self.entity_description.is_on_fn(self.hub, self.resource_id)

@callback
def _resource_id_from_trouble_condition(hub: AlarmHub, condition: pyadc.trouble_condition.TroubleCondition) -> str | None:
    """Resolve a managed device resource ID from a trouble condition."""

    ember_device_id = condition.attributes.ember_device_id
    if ember_device_id and ember_device_id in hub.api.managed_devices:
        return ember_device_id

    device_id = condition.attributes.device_id
    if device_id is None:
        return None

    device_id_str = str(device_id)
    for resource_id in hub.api.managed_devices:
        if resource_id == device_id_str or resource_id.endswith(f"-{device_id_str}"):
            return resource_id

    return None

@callback
def _conditions_for_resource(
    hub: AlarmHub,
    resource_id: str,
) -> list[pyadc.trouble_condition.TroubleCondition]:
    """Return all active trouble conditions for a managed device."""

    return [
        condition
        for condition in hub.api.trouble_conditions
        if _resource_id_from_trouble_condition(hub, condition) == resource_id
    ]

SYSTEM_TROUBLE_SENSORS: list[tuple[pyadc.trouble_condition.TroubleConditionType, str]] = [
    (pyadc.trouble_condition.TroubleConditionType.ACFailure, "AC Failure"),
    (pyadc.trouble_condition.TroubleConditionType.SensorLowBattery, "Sensor Low Battery"),
    (pyadc.trouble_condition.TroubleConditionType.PanelLowBattery, "Panel Low Battery"),
    (pyadc.trouble_condition.TroubleConditionType.PanelNotResponding, "Panel Not Responding"),
    (pyadc.trouble_condition.TroubleConditionType.CameraNotReachable, "Camera Not Reachable"),
    (pyadc.trouble_condition.TroubleConditionType.WaterAlert, "Water Alert"),
    (pyadc.trouble_condition.TroubleConditionType.AlarmInMemory, "Alarm In Memory"),
    (pyadc.trouble_condition.TroubleConditionType.SmokeSensorReset, "Smoke Sensor Reset"),
    (pyadc.trouble_condition.TroubleConditionType.BatteryCharging, "Battery Charging"),
    (pyadc.trouble_condition.TroubleConditionType.SensorNotResponding, "Sensor Not Responding"),
]

class TroubleConditionBinarySensorEntity(BinarySensorEntity):
    """System-level Alarm.com trouble condition binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        hub: AlarmHub,
        resource_id: str,
        trouble_type: pyadc.trouble_condition.TroubleConditionType,
        name: str,
    ) -> None:
        """Initialize the trouble condition entity."""

        self.hub = hub
        self.resource_id = resource_id
        self.trouble_type = trouble_type
        self._attr_name = f"{hub.api.active_system.name} {name}"
        self._attr_unique_id = f"{resource_id}_trouble_{trouble_type.name.lower()}"
        self._attr_available = hub.available
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, resource_id)})
        self._attr_is_on = self._has_active_trouble()

    @property
    def extra_state_attributes(self) -> dict[str, str | int | list[str | None] | None]:
        """Return extra state attributes for the active trouble conditions."""

        matching_conditions = [
            condition
            for condition in self.hub.api.trouble_conditions
            if condition.attributes.trouble_condition_type == self.trouble_type
        ]

        return {
            "active_count": len(matching_conditions),
            "condition_ids": [condition.id for condition in matching_conditions],
            "subtypes": [
                condition.attributes.trouble_condition_sub_type.name
                if condition.attributes.trouble_condition_sub_type is not None
                else None
                for condition in matching_conditions
            ],
        }

    @callback
    def _has_active_trouble(self) -> bool:
        """Return whether the trouble condition is currently active."""

        return any(
            condition.attributes.trouble_condition_type == self.trouble_type
            for condition in self.hub.api.trouble_conditions
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        self.async_on_remove(self.hub.api.subscribe(self.event_handler))

    @callback
    def event_handler(self, message: pyadc.EventBrokerMessage) -> None:
        """Handle event message."""

        if message.topic in [
            pyadc.EventBrokerTopic.RESOURCE_ADDED,
            pyadc.EventBrokerTopic.RESOURCE_UPDATED,
            pyadc.EventBrokerTopic.RESOURCE_DELETED,
            pyadc.EventBrokerTopic.CONNECTION_EVENT,
        ]:
            self._attr_available = self.hub.available
            self._attr_is_on = self._has_active_trouble()
            self.async_write_ha_state()

class DeviceTroubleBinarySensorEntity(BinarySensorEntity):
    """Device-level Alarm.com trouble condition binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, hub: AlarmHub, resource_id: str) -> None:
        """Initialize the device trouble entity."""

        self.hub = hub
        self.resource_id = resource_id
        self._attr_name = "Trouble"
        self._attr_unique_id = f"{resource_id}_trouble"
        self._attr_available = hub.available
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, resource_id)})
        self._attr_is_on = self._has_active_trouble()

    @property
    def extra_state_attributes(self) -> dict[str, str | int | list[str | None] | None]:
        """Return extra state attributes for active device trouble conditions."""

        matching_conditions = _conditions_for_resource(self.hub, self.resource_id)

        return {
            "active_count": len(matching_conditions),
            "condition_ids": [condition.id for condition in matching_conditions],
            "trouble_types": [
                condition.attributes.trouble_condition_type.name
                if condition.attributes.trouble_condition_type is not None
                else None
                for condition in matching_conditions
            ],
            "subtypes": [
                condition.attributes.trouble_condition_sub_type.name
                if condition.attributes.trouble_condition_sub_type is not None
                else None
                for condition in matching_conditions
            ],
        }

    @callback
    def _has_active_trouble(self) -> bool:
        """Return whether the device currently has any active trouble condition."""

        return bool(_conditions_for_resource(self.hub, self.resource_id))

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        self.async_on_remove(self.hub.api.subscribe(self.event_handler))

    @callback
    def event_handler(self, message: pyadc.EventBrokerMessage) -> None:
        """Handle event message."""

        if message.topic in [
            pyadc.EventBrokerTopic.RESOURCE_ADDED,
            pyadc.EventBrokerTopic.RESOURCE_UPDATED,
            pyadc.EventBrokerTopic.RESOURCE_DELETED,
            pyadc.EventBrokerTopic.CONNECTION_EVENT,
        ]:
            self._attr_available = self.hub.available
            self._attr_is_on = self._has_active_trouble()
            self.async_write_ha_state()
