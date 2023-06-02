"""Alarmdotcom implementation of an HA lock."""
from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

from homeassistant import config_entries, core
from homeassistant.components import persistent_notification
from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback, DiscoveryInfoType
from homeassistant.helpers.typing import ConfigType
from pyalarmdotcomajax.devices.lock import Lock as libLock
from pyalarmdotcomajax.exceptions import NotAuthorized

from .base_device import HardwareBaseDevice
from .const import CONF_ARM_CODE, DATA_CONTROLLER, DOMAIN, MIGRATE_MSG_ALERT
from .controller import AlarmIntegrationController

log = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the legacy platform."""

    log.debug("Alarmdotcom: Detected legacy lock config entry. Converting to Home Assistant config flow.")

    hass.async_create_task(
        hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config)
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

    controller: AlarmIntegrationController = hass.data[DOMAIN][config_entry.entry_id][DATA_CONTROLLER]

    async_add_entities(
        Lock(
            controller=controller,
            device=device,
        )
        for device in controller.api.devices.locks.values()
    )


class Lock(HardwareBaseDevice, LockEntity):  # type: ignore
    """Integration Lock Entity."""

    _device_type_name: str = "Lock"
    _device: libLock

    def __init__(
        self,
        controller: AlarmIntegrationController,
        device: libLock,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(controller, device, device.partition_id)

        self._attr_code_format = (
            self._determine_code_format(code) if (code := controller.options.get(CONF_ARM_CODE)) else ""
        )

    @callback
    def _update_device_data(self) -> None:
        """Update the entity when coordinator is updated."""

        self._attr_is_locked = self._determine_is_locked(self._device.state)
        self._attr_is_locking = False
        self._attr_is_unlocking = False

    def _determine_is_locked(self, state: Enum | None) -> bool | None:
        """Return true if the lock is locked."""

        log.info("Processing is_locked %s for %s", state, self.name or self._device.name)

        if self._device.malfunction or not state:
            return None

        match state:
            case libLock.DeviceState.LOCKED:
                return True
            case libLock.DeviceState.UNLOCKED:
                return False
            case _:
                log.error(f"Cannot determine whether {self.name} is locked. Found raw state of {state}.")
                return None

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        if self._validate_code(kwargs.get("code")):
            self._attr_is_locking = True

            try:
                await self._device.async_lock()
            except NotAuthorized:
                self._show_permission_error("lock")

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        if self._validate_code(kwargs.get("code")):
            self._attr_is_unlocking = True

            try:
                await self._device.async_unlock()
            except NotAuthorized:
                self._show_permission_error("unlock")

    #
    # Helpers
    #

    @classmethod
    def _determine_code_format(cls, code: str) -> str:
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
        check: bool | str = (arm_code := self._controller.options.get(CONF_ARM_CODE)) in [
            None,
            "",
        ] or code == arm_code
        if not check:
            log.warning("Wrong code entered.")
        return check
