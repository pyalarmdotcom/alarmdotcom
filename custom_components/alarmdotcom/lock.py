"""Alarmdotcom implementation of an HA lock."""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant import config_entries
from homeassistant import core
from homeassistant.components import persistent_notification
from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from homeassistant.helpers.typing import ConfigType
from pyalarmdotcomajax.devices import BaseDevice as libBaseDevice
from pyalarmdotcomajax.devices.lock import Lock as libLock

from .alarmhub import AlarmHub
from .base_device import HardwareBaseDevice
from .const import CONF_ARM_CODE
from .const import DOMAIN
from .const import MIGRATE_MSG_ALERT

log = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the legacy platform."""

    log.debug(
        "Alarmdotcom: Detected legacy lock config entry. Converting to Home"
        " Assistant config flow."
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
    )

    log.warning(MIGRATE_MSG_ALERT)

    persistent_notification.async_create(
        hass,
        MIGRATE_MSG_ALERT,
        title="Alarm.com Updated",
        notification_id="alarmdotcom_migration",
    )


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the lock platform."""

    alarmhub: Lock = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Lock(
            alarmhub=alarmhub,
            device=device,
        )
        for device in alarmhub.system.locks
    )


class Lock(HardwareBaseDevice, LockEntity):  # type: ignore
    """Integration Lock Entity."""

    _device_type_name: str = "Lock"
    _device: libLock

    def __init__(
        self,
        alarmhub: AlarmHub,
        device: libBaseDevice,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(alarmhub, device, device.partition_id)

        self._attr_code_format = (
            self._determine_code_format(code)
            if (code := alarmhub.options.get(CONF_ARM_CODE))
            else ""
        )

    @callback  # type: ignore
    def update_device_data(self) -> None:
        """Update the entity when coordinator is updated."""

        self._attr_is_locked = self._determine_is_locked(self._device.state)
        self._attr_is_locking = False
        self._attr_is_unlocking = False

    def _determine_is_locked(self, state: libLock.DeviceState) -> bool | None:
        """Return true if the lock is locked."""

        if not self._device.malfunction:

            if state == libLock.DeviceState.LOCKED:
                return True

            if state == libLock.DeviceState.UNLOCKED:
                return False

        return None

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        if self._validate_code(kwargs.get("code")):

            self._attr_is_locking = True

            try:
                await self._device.async_lock()
            except PermissionError:
                self._show_permission_error("lock")

            await self._alarmhub.coordinator.async_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        if self._validate_code(kwargs.get("code")):

            self._attr_is_unlocking = True

            try:
                await self._device.async_unlock()
            except PermissionError:
                self._show_permission_error("unlock")

            await self._alarmhub.coordinator.async_refresh()

    #
    # Helpers
    #

    @classmethod
    def _determine_code_format(cls, code: str) -> str:

        if isinstance(code, str):

            code_patterns = [
                r"^\d+$",  # Only digits
                r"^\w\D+$",  # Only alpha
                r"^\w+$",  # Alphanumeric
            ]

            for pattern in code_patterns:
                if re.findall(pattern, code):
                    return pattern

            return "."  # All characters

    def _validate_code(self, code: str | None) -> bool | str:
        """Validate given code."""
        check: bool | str = (arm_code := self._alarmhub.options.get(CONF_ARM_CODE)) in [
            None,
            "",
        ] or code == arm_code
        if not check:
            log.warning("Wrong code entered.")
        return check
