"""Interfaces with Alarm.com locks."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic

import pyalarmdotcomajax as pyadc
from homeassistant.components.lock import (
    LockEntity,
    LockEntityDescription,
    LockEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DATA_HUB, DOMAIN
from .entity import AdcControllerT, AdcEntity, AdcEntityDescription, AdcManagedDeviceT
from .util import cleanup_orphaned_entities_and_devices

if TYPE_CHECKING:
    from .hub import AlarmHub

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the lock platform."""

    hub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id][DATA_HUB]

    entities = [
        AdcLockEntity(hub=hub, resource_id=device.id, description=entity_description)
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
def code_format_fn(hub: AlarmHub) -> str | None:
    """Return the format of the code, if any."""

    if arm_code := hub.config_entry.options.get("arm_code"):
        import re

        code_patterns = [
            r"^\d+$",  # Only digits
            r"^\w\D+$",  # Only alpha
            r"^\w+$",  # Alphanumeric
        ]
        for pattern in code_patterns:
            if re.fullmatch(pattern, arm_code):
                return pattern
        return "."  # All characters
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
    code_format_fn: Callable[[AlarmHub], str | None]
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

    def _validate_code(self, code: str | None) -> bool:
        arm_code = (
            self.hub.config_entry.options.get("arm_code")
            if hasattr(self.hub, "config_entry")
            else None
        )
        if arm_code in [None, ""] or code == arm_code:
            return True
        log.warning("Wrong code entered for lock %s.", self.resource_id)
        return False

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
        code = kwargs.get("code")
        if self._validate_code(code):
            await self.entity_description.control_fn(
                self.controller, self.resource_id, "lock"
            )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Send unlock command."""
        code = kwargs.get("code")
        if self._validate_code(code):
            await self.entity_description.control_fn(
                self.controller, self.resource_id, "unlock"
            )
