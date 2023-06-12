"""Alarmdotcom implementation of an HA lock."""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant import config_entries, core
from homeassistant.components import persistent_notification
from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback, DiscoveryInfoType
from homeassistant.helpers.typing import ConfigType
from pyalarmdotcomajax.devices.lock import Lock as libLock
from pyalarmdotcomajax.exceptions import NotAuthorized

from .base_device import HardwareBaseDevice
from .const import CONF_ARM_CODE, DATA_CONTROLLER, DOMAIN, MIGRATE_MSG_ALERT
from .controller import AlarmIntegrationController

LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the legacy platform."""

    LOGGER.debug("Alarmdotcom: Detected legacy lock config entry. Converting to Home Assistant config flow.")

    hass.async_create_task(
        hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config)
    )

    LOGGER.warning(MIGRATE_MSG_ALERT)

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

    @property
    def code_format(self) -> str | None:
        """Return the format of the code."""

        if code := self._controller.options.get(CONF_ARM_CODE):
            code_patterns = [
                r"^\d+$",  # Only digits
                r"^\w\D+$",  # Only alpha
                r"^\w+$",  # Alphanumeric
            ]

            for pattern in code_patterns:
                if re.findall(pattern, code):
                    return pattern

            return "."  # All characters

        return None

    @property
    def is_locking(self) -> bool | None:
        """Return true if lock is locking."""

        return (
            not self._device.malfunction
            and self._device.state == libLock.DeviceState.UNLOCKED
            and self._device.desired_state == libLock.DeviceState.LOCKED
        )

    @property
    def is_unlocking(self) -> bool | None:
        """Return true if lock is unlocking."""

        return (
            not self._device.malfunction
            and self._device.desired_state == libLock.DeviceState.UNLOCKED
            and self._device.state == libLock.DeviceState.LOCKED
        )

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is locked."""

        # LOGGER.info("Processing is_locked %s for %s", self._device.state, self.name or self._device.name)

        if not self._device.malfunction:
            match self._device.state:
                case libLock.DeviceState.LOCKED:
                    return True
                case libLock.DeviceState.UNLOCKED:
                    return False
                case _:
                    LOGGER.error(
                        f"Cannot determine whether {self.name} is locked. Found raw state of {self._device.state}."
                    )

        return None

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        if self._validate_code(kwargs.get("code")):
            try:
                await self._device.async_lock()
            except NotAuthorized:
                self._show_permission_error("lock")

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        if self._validate_code(kwargs.get("code")):
            try:
                await self._device.async_unlock()
            except NotAuthorized:
                self._show_permission_error("unlock")

    #
    # Helpers
    #

    def _validate_code(self, code: str | None) -> bool | str:
        """Validate given code."""
        check: bool | str = (arm_code := self._controller.options.get(CONF_ARM_CODE)) in [
            None,
            "",
        ] or code == arm_code
        if not check:
            LOGGER.warning("Wrong code entered.")
        return check
