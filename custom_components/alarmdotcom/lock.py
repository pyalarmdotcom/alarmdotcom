"""Interfaces with Alarm.com locks."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic

import _pyalarmdotcomajax as pyadc
from homeassistant.components.alarm_control_panel import CodeFormat
from homeassistant.components.lock import (
    LockEntity,
    LockEntityDescription,
    LockEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .entity import AdcControllerT, AdcEntity, AdcEntityDescription, AdcManagedDeviceT
from .util import cleanup_orphaned_entities_and_devices

if TYPE_CHECKING:
    from .activity_history import ActivityFeedTracker
    from .hub import AlarmHub

# Entities are updated via push (websocket events), not per-entity polling -
# PARALLEL_UPDATES has no effect on update frequency here, but setting it
# to 0 is still the correct, explicit signal for a push-based integration.
PARALLEL_UPDATES = 0

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the lock platform."""

    hub: AlarmHub = config_entry.runtime_data.hub
    lock_activity_tracker: ActivityFeedTracker = config_entry.runtime_data.activity_feed_tracker

    entities: list[AdcLockEntity] = [
        AdcLockEntity(
            hub=hub,
            resource_id=device.id,
            description=entity_description,
            lock_activity_tracker=lock_activity_tracker,
        )
        for entity_description in ENTITY_DESCRIPTIONS
        for device in hub.api.locks
        if entity_description.supported_fn(hub, device.id)
    ]
    async_add_entities(entities)

    current_entity_ids = {entity.entity_id for entity in entities}
    current_unique_ids = {
        uid for uid in (entity.unique_id for entity in entities) if uid is not None
    }
    await cleanup_orphaned_entities_and_devices(
        hass, config_entry, current_entity_ids, current_unique_ids, "lock"
    )


@callback
def is_locked_fn(hub: AlarmHub, lock_id: str) -> bool:
    """Return whether the lock is locked."""

    resource = hub.api.locks[lock_id]
    return resource.attributes.state == pyadc.lock.LockState.LOCKED


@callback
def is_locking_fn(hub: AlarmHub, lock_id: str) -> bool:
    """Return whether the lock is in the process of locking."""

    resource = hub.api.locks[lock_id]
    return (
        resource.attributes.state != pyadc.lock.LockState.LOCKED
        and resource.attributes.desired_state == pyadc.lock.LockState.LOCKED
    )


@callback
def is_unlocking_fn(hub: AlarmHub, lock_id: str) -> bool:
    """Return whether the lock is in the process of unlocking."""

    resource = hub.api.locks[lock_id]
    return (
        resource.attributes.state != pyadc.lock.LockState.UNLOCKED
        and resource.attributes.desired_state == pyadc.lock.LockState.UNLOCKED
    )


@callback
def supported_features_fn(
    controller: pyadc.LockController, lock_id: str
) -> LockEntityFeature:
    """Return the supported features for the lock."""

    # We don't support the OPEN state, just LOCKED and UNLOCKED.
    return LockEntityFeature(0)


@callback
async def control_fn(
    controller: pyadc.LockController,
    lock_id: str,
    command: str,
) -> None:
    """Lock or unlock the device."""

    try:
        if command == "lock":
            await controller.lock(lock_id)
        elif command == "unlock":
            await controller.unlock(lock_id)
        else:
            raise ValueError(f"Unsupported command: {command}")
    except (pyadc.ServiceUnavailable, pyadc.UnexpectedResponse) as err:
        log.error("Failed to execute lock command: %s", err)
        raise


@callback
def code_format_fn(hub: AlarmHub) -> CodeFormat | None:
    """
    Return the code format for the lock.

    Locks do not require a code to operate from Home Assistant by default.
    The arm_code integration option applies to the alarm control panel only.
    Returning None means HA will not prompt for a code on lock/unlock actions.
    """
    return None


@dataclass(frozen=True, kw_only=True)
class AdcLockEntityDescription(
    Generic[AdcManagedDeviceT, AdcControllerT],
    AdcEntityDescription[AdcManagedDeviceT, AdcControllerT],
    LockEntityDescription,
):
    """Base Alarm.com lock entity description."""

    is_locked_fn: Callable[[AlarmHub, str], bool]
    """Return whether the lock is locked."""
    is_locking_fn: Callable[[AlarmHub, str], bool]
    """Return whether the lock is locking."""
    is_unlocking_fn: Callable[[AlarmHub, str], bool]
    """Return whether the lock is unlocking."""
    code_format_fn: Callable[[AlarmHub], CodeFormat | None]
    """Return the format of the code, if any."""
    supported_features_fn: Callable[[AdcControllerT, str], LockEntityFeature]
    """Return the supported features for the lock."""
    control_fn: Callable[[AdcControllerT, str, str], Coroutine[Any, Any, None]]
    """Lock or unlock the device."""


ENTITY_DESCRIPTIONS: list[
    AdcLockEntityDescription[pyadc.lock.Lock, pyadc.LockController]
] = [
    AdcLockEntityDescription(
        key="locks",
        controller_fn=lambda hub, _: hub.api.locks,
        is_locked_fn=is_locked_fn,
        is_locking_fn=is_locking_fn,
        is_unlocking_fn=is_unlocking_fn,
        supported_features_fn=supported_features_fn,
        code_format_fn=code_format_fn,
        control_fn=control_fn,
    )
]


class AdcLockEntity(AdcEntity[AdcManagedDeviceT, AdcControllerT], LockEntity):
    """Base Alarm.com lock entity."""

    entity_description: AdcLockEntityDescription

    def __init__(
        self,
        hub: AlarmHub,
        resource_id: str,
        description: AdcLockEntityDescription,
        lock_activity_tracker: ActivityFeedTracker,
    ) -> None:
        """Initialize the lock entity, additionally wiring in the lock activity tracker."""

        self._lock_activity_tracker = lock_activity_tracker
        super().__init__(hub=hub, resource_id=resource_id, description=description)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """
        Return this entity's extra attributes, plus unlock attribution/method, if known.

        Computed live (not set once in __init__) since new attribution
        arrives on the lock activity tracker's own polling cadence, not
        the resource-update events the rest of this entity's state
        responds to. These are deliberately omitted entirely (not set to
        None) when nothing has been tracked yet, rather than always
        showing a possibly-stale or empty value.

        last_unlock_method exists specifically because last_unlocked_by
        alone isn't reliable for gating an automation on "was this a
        keypad entry" (real user feedback, GitHub issue #79): not every
        unlock method generates its own loggable Alarm.com event for
        every lock model, so last_unlocked_by can remain stuck showing an
        earlier keypad user's name well after a different, unattributed
        unlock. last_unlock_method reflects whatever the most recent
        tracked unlock actually was, independent of that staleness.
        """

        attrs = dict(self._attr_extra_state_attributes or {})
        last_unlock = self._lock_activity_tracker.get_last_unlock(self.resource_id)
        if last_unlock is not None:
            attrs["last_unlocked_by"] = last_unlock["unlocked_by"]
            attrs["last_unlock_method"] = last_unlock["unlock_method"]
            attrs["last_unlocked_at"] = last_unlock["unlocked_at"].isoformat()
        return attrs

    async def async_added_to_hass(self) -> None:
        """Subscribe to resource updates (via the base class) and lock activity attribution changes."""

        await super().async_added_to_hass()
        self.async_on_remove(self._lock_activity_tracker.add_listener(self._on_activity_change))

    @callback
    def _on_activity_change(self) -> None:
        """Push updated state when the lock activity tracker finds new unlock attribution."""

        self.async_write_ha_state()

    @callback
    def initiate_state(self) -> None:
        """Initiate entity state."""

        self._attr_is_locked = self.entity_description.is_locked_fn(
            self.hub, self.resource_id
        )
        self._attr_is_locking = self.entity_description.is_locking_fn(
            self.hub, self.resource_id
        )
        self._attr_is_unlocking = self.entity_description.is_unlocking_fn(
            self.hub, self.resource_id
        )
        self._attr_supported_features = self.entity_description.supported_features_fn(
            self.controller, self.resource_id
        )
        self._attr_code_format = self.entity_description.code_format_fn(self.hub)

        super().initiate_state()

    @callback
    def update_state(self, message: pyadc.EventBrokerMessage | None = None) -> None:
        """Update entity state."""

        if isinstance(message, pyadc.ResourceEventMessage):
            self._attr_is_locked = self.entity_description.is_locked_fn(
                self.hub, self.resource_id
            )
            self._attr_is_locking = self.entity_description.is_locking_fn(
                self.hub, self.resource_id
            )
            self._attr_is_unlocking = self.entity_description.is_unlocking_fn(
                self.hub, self.resource_id
            )

    async def async_lock(self, **kwargs: Any) -> None:
        """Send lock command."""
        await self.entity_description.control_fn(
            self.controller, self.resource_id, "lock"
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Send unlock command."""
        await self.entity_description.control_fn(
            self.controller, self.resource_id, "unlock"
        )
