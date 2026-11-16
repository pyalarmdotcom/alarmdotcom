"""Interfaces with Alarm.com sensors."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic

import _pyalarmdotcomajax as pyadc
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN
from .entity import (
    AdcControllerT,
    AdcEntity,
    AdcEntityDescription,
    AdcManagedDeviceT,
)
from .util import cleanup_orphaned_entities_and_devices

if TYPE_CHECKING:
    from .activity_history import ActivityFeedTracker
    from .auto_off import AutoOffManager
    from .hub import AlarmHub

# Entities are updated via push (websocket events), not per-entity polling -
# PARALLEL_UPDATES has no effect on update frequency here, but setting it
# to 0 is still the correct, explicit signal for a push-based integration.
PARALLEL_UPDATES = 0

log = logging.getLogger(__name__)

BATTERY_CLASSIFICATION_LABELS: dict[pyadc.base.BatteryLevel, str] = {
    pyadc.base.BatteryLevel.CRITICAL: "Critical",
    pyadc.base.BatteryLevel.LOW: "Low",
    pyadc.base.BatteryLevel.MEDIUM: "Medium",
    pyadc.base.BatteryLevel.HIGH: "High",
    pyadc.base.BatteryLevel.NONE: "None",
}

BATTERY_CLASSIFICATION_OPTIONS = list(BATTERY_CLASSIFICATION_LABELS.values())


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    hub: AlarmHub = config_entry.runtime_data.hub
    auto_off_manager: AutoOffManager = config_entry.runtime_data.auto_off_manager
    activity_feed_tracker: ActivityFeedTracker = config_entry.runtime_data.activity_feed_tracker

    entities: list[AdcSensorEntity] = []
    for entity_description in ENTITY_DESCRIPTIONS:
        entities.extend(
            AdcSensorEntity(hub=hub, resource_id=device.id, description=entity_description)
            for device in hub.api.managed_devices.values()
            if entity_description.supported_fn(hub, device.id)
        )

    battery_summary_entities: list[AdcBatterySummarySensor] = [
        AdcBatterySummarySensor(hub=hub, level=pyadc.base.BatteryLevel.LOW, name="Low Battery Count"),
        AdcBatterySummarySensor(hub=hub, level=pyadc.base.BatteryLevel.CRITICAL, name="Critical Battery Count"),
    ]

    auto_off_summary_entities: list[AdcActiveAutoOffTimersSensor] = [
        AdcActiveAutoOffTimersSensor(hub=hub, auto_off_manager=auto_off_manager),
    ]

    activity_feed_entities: list[AdcRecentActivitySensor] = [
        AdcRecentActivitySensor(hub=hub, activity_feed_tracker=activity_feed_tracker),
    ]

    all_entities = [*entities, *battery_summary_entities, *auto_off_summary_entities, *activity_feed_entities]
    async_add_entities(all_entities)

    current_entity_ids = {entity.entity_id for entity in all_entities}
    current_unique_ids = {uid for uid in (entity.unique_id for entity in all_entities) if uid is not None}
    await cleanup_orphaned_entities_and_devices(hass, config_entry, current_entity_ids, current_unique_ids, "sensor")


@callback
def battery_percentage_supported_fn(hub: AlarmHub, resource_id: str) -> bool:
    """Check if the battery percentage sensor is supported."""

    resource = hub.api.managed_devices.get(resource_id)
    if resource is None:
        return False

    return getattr(resource.attributes, "battery_level_pct", None) is not None


@callback
def battery_percentage_native_value_fn(hub: AlarmHub, resource_id: str) -> int | None:
    """Return the native battery percentage value."""

    resource = hub.api.managed_devices.get(resource_id)
    if resource is None:
        return None

    return getattr(resource.attributes, "battery_level_pct", None)


@callback
def battery_classification_supported_fn(hub: AlarmHub, resource_id: str) -> bool:
    """Check if the battery classification sensor is supported."""

    resource = hub.api.managed_devices.get(resource_id)
    if resource is None:
        return False

    classification = getattr(resource.attributes, "battery_level_classification", None)
    return classification is not None


@callback
def battery_classification_native_value_fn(hub: AlarmHub, resource_id: str) -> str | None:
    """Return the battery classification label."""

    resource = hub.api.managed_devices.get(resource_id)
    if resource is None:
        return None

    classification = getattr(resource.attributes, "battery_level_classification", None)
    if classification is None:
        return None

    return BATTERY_CLASSIFICATION_LABELS.get(classification, str(classification).title())


@dataclass(frozen=True, kw_only=True)
class AdcSensorEntityDescription(
    Generic[AdcManagedDeviceT, AdcControllerT],
    AdcEntityDescription[AdcManagedDeviceT, AdcControllerT],
    SensorEntityDescription,
):
    """Base Alarm.com sensor entity description."""

    native_value_fn: Callable[[AlarmHub, str], str | int | None]
    """Return the sensor native value."""


ENTITY_DESCRIPTIONS: list[AdcSensorEntityDescription] = [
    AdcSensorEntityDescription[pyadc.base.AdcDeviceResource, pyadc.BaseController](
        key="battery_level_pct",
        controller_fn=lambda hub, resource_id: hub.api.get_controller(resource_id),
        name="Battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        supported_fn=battery_percentage_supported_fn,
        native_value_fn=battery_percentage_native_value_fn,
    ),
    AdcSensorEntityDescription[pyadc.base.AdcDeviceResource, pyadc.BaseController](
        key="battery_level_classification",
        controller_fn=lambda hub, resource_id: hub.api.get_controller(resource_id),
        name="Battery Status",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=BATTERY_CLASSIFICATION_OPTIONS,
        supported_fn=battery_classification_supported_fn,
        native_value_fn=battery_classification_native_value_fn,
    ),
]


class AdcSensorEntity(AdcEntity[AdcManagedDeviceT, AdcControllerT], SensorEntity):
    """Base Alarm.com sensor entity."""

    entity_description: AdcSensorEntityDescription

    @callback
    def initiate_state(self) -> None:
        """Initiate entity state."""

        self._attr_native_value = self.entity_description.native_value_fn(self.hub, self.resource_id)

        super().initiate_state()

    @callback
    def update_state(self, message: pyadc.EventBrokerMessage | None = None) -> None:
        """Update entity state."""

        if isinstance(message, pyadc.ResourceEventMessage):
            self._attr_native_value = self.entity_description.native_value_fn(self.hub, self.resource_id)


class AdcBatterySummarySensor(SensorEntity):
    """
    Aggregate count of devices at a given battery-level classification, account-wide.

    Unlike every other entity in this platform, this is a single, permanent
    entity per classification (not one per device) - it doesn't fit the
    per-resource_id AdcEntity base class, which is hard-wired to react to
    updates for one specific device. Subscribes with ids=None (matching
    AlarmBridge.subscribe's own documented "all resource controllers"
    behavior) so it recomputes whenever any device's battery status
    changes, not just at startup.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "devices"

    def __init__(self, hub: AlarmHub, level: pyadc.base.BatteryLevel, name: str) -> None:
        """Initialize the battery summary sensor."""

        self.hub = hub
        self._level = level
        self._attr_name = name
        self._attr_unique_id = f"{hub.config_entry.entry_id}_battery_summary_{level.name.lower()}"

        system_id = getattr(hub.api.active_system, "id", None)
        self._attr_device_info = (
            DeviceInfo(identifiers={(DOMAIN, system_id)}) if isinstance(system_id, str) else None
        )

        self._recompute()

    @callback
    def _recompute(self, message: pyadc.EventBrokerMessage | None = None) -> None:
        """Recount matching devices and refresh the device-name attribute list."""

        matching = [
            device
            for device in self.hub.api.managed_devices.values()
            if getattr(device.attributes, "battery_level_classification", None) == self._level
        ]
        self._attr_native_value = len(matching)
        self._attr_extra_state_attributes = {"devices": sorted(device.name for device in matching)}

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates for every resource, not just one device."""

        self.async_on_remove(self.hub.api.subscribe(self._event_handler, None))

    @callback
    def _event_handler(self, message: pyadc.EventBrokerMessage) -> None:
        """Recompute and push state on any resource add/update - mirrors AdcEntity.event_handler."""

        if message.topic in (
            pyadc.EventBrokerTopic.RESOURCE_ADDED,
            pyadc.EventBrokerTopic.RESOURCE_UPDATED,
        ):
            self._recompute(message)
            self.async_write_ha_state()


class AdcActiveAutoOffTimersSensor(SensorEntity):
    """
    Count of currently-pending auto-off timers, account-wide.

    Same architecture as AdcBatterySummarySensor (a single, permanent,
    account-level entity rather than one per device) but reacts to a
    different source of change: AutoOffManager's own listener mechanism,
    since a timer being set or cancelled via the set_auto_off/cancel_auto_off
    services isn't an Alarm.com resource event at all - hub.api.subscribe
    would never see it.
    """

    _attr_has_entity_name = True
    _attr_name = "Active Auto-Off Timers"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "timers"
    _attr_icon = "mdi:timer-outline"

    def __init__(self, hub: AlarmHub, auto_off_manager: AutoOffManager) -> None:
        """Initialize the active auto-off timers sensor."""

        self.hub = hub
        self._auto_off_manager = auto_off_manager
        self._attr_unique_id = f"{hub.config_entry.entry_id}_active_auto_off_timers"

        system_id = getattr(hub.api.active_system, "id", None)
        self._attr_device_info = (
            DeviceInfo(identifiers={(DOMAIN, system_id)}) if isinstance(system_id, str) else None
        )

        self._recompute()

    @callback
    def _recompute(self) -> None:
        """Recount active timers and refresh the per-light off-time attribute list."""

        active = self._auto_off_manager.get_all_active()
        self._attr_native_value = len(active)
        self._attr_extra_state_attributes = {
            "timers": {
                self._friendly_name(entity_id): off_at.isoformat()
                for entity_id, off_at in sorted(active.items(), key=lambda item: item[1])
            }
        }

    def _friendly_name(self, entity_id: str) -> str:
        """Return the light's current friendly name, falling back to its entity_id if unavailable."""

        state = self.hub.hass.states.get(entity_id)
        return state.name if state is not None else entity_id

    async def async_added_to_hass(self) -> None:
        """Subscribe to the auto-off manager's own change notifications."""

        self.async_on_remove(self._auto_off_manager.add_listener(self._on_change))

    @callback
    def _on_change(self) -> None:
        """Recompute and push state whenever a timer is set, cancelled, or fires."""

        self._recompute()
        self.async_write_ha_state()


class AdcRecentActivitySensor(SensorEntity):
    """
    Most recent curated Alarm.com activity event, account-wide, with a short rolling history attribute.

    Same account-wide singleton architecture as AdcBatterySummarySensor and
    AdcActiveAutoOffTimersSensor, reacting to ActivityFeedTracker's own
    listener mechanism (the same one lock unlock attribution uses) rather
    than hub.api.subscribe - a curated activity event is sourced from
    Alarm.com's activity history endpoint, not a live resource-update
    event, so hub.api.subscribe would never see it.
    """

    _attr_has_entity_name = True
    _attr_name = "Recent Activity"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:history"

    def __init__(self, hub: AlarmHub, activity_feed_tracker: ActivityFeedTracker) -> None:
        """Initialize the recent activity sensor."""

        self.hub = hub
        self._activity_feed_tracker = activity_feed_tracker
        self._attr_unique_id = f"{hub.config_entry.entry_id}_recent_activity"

        system_id = getattr(hub.api.active_system, "id", None)
        self._attr_device_info = (
            DeviceInfo(identifiers={(DOMAIN, system_id)}) if isinstance(system_id, str) else None
        )

        self._recompute()

    @callback
    def _recompute(self) -> None:
        """Refresh the current-value description and the recent-events attribute list."""

        recent = self._activity_feed_tracker.get_recent_activity()
        self._attr_native_value = recent[0]["description"] if recent else "No recent activity"
        self._attr_extra_state_attributes = {"recent_events": recent}

    async def async_added_to_hass(self) -> None:
        """Subscribe to the activity feed tracker's own change notifications."""

        self.async_on_remove(self._activity_feed_tracker.add_listener(self._on_change))

    @callback
    def _on_change(self) -> None:
        """Recompute and push state whenever new curated activity is found."""

        self._recompute()
        self.async_write_ha_state()
