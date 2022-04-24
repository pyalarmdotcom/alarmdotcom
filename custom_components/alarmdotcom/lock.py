"""Alarmdotcom implementation of an HA lock."""
from __future__ import annotations

from collections.abc import Callable
import logging
import re
from typing import Any

from homeassistant import config_entries
from homeassistant import core
from homeassistant.components import lock
from homeassistant.components import persistent_notification
from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from homeassistant.helpers.typing import ConfigType
from pyalarmdotcomajax.entities import ADCLock

from . import ADCIEntity
from . import const as adci
from .controller import ADCIController

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
            adci.DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
    )

    log.warning(adci.MIGRATE_MSG_ALERT)

    persistent_notification.async_create(
        hass,
        adci.MIGRATE_MSG_ALERT,
        title="Alarm.com Updated",
        notification_id="alarmdotcom_migration",
    )


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    controller: ADCIController = hass.data[adci.DOMAIN][config_entry.entry_id]

    async_add_entities(
        ADCILock(controller, controller.devices.get("entity_data", {}).get(lock_id))  # type: ignore
        for lock_id in controller.devices.get("lock_ids", [])
    )


class ADCILock(ADCIEntity, LockEntity):  # type: ignore
    """Integration Lock Entity."""

    _device_type_name: str = "Lock"

    def __init__(
        self, controller: ADCIController, device_data: adci.ADCILockData
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(controller, device_data)

        self._arm_code: str | None = self._controller.config_entry.options.get(
            "arm_code"
        )

        self._device: adci.ADCILockData = device_data

        try:
            self.async_lock_callback: Callable = self._device["async_lock_callback"]
            self.async_unlock_callback: Callable = self._device["async_unlock_callback"]
        except KeyError:
            log.error("Failed to initialize control functions for %s.", self.unique_id)
            self._attr_available = False

        log.debug(
            "%s: Initializing Alarm.com lock entity for lock %s.",
            __name__,
            self.unique_id,
        )

    @property
    def code_format(self) -> str | None:
        """Return one or more digits/characters."""
        if self._arm_code is None:
            return None
        if isinstance(self._arm_code, str) and re.search("^\\d+$", self._arm_code):
            return str(lock.ATTR_CODE_FORMAT)
        return str(lock.ATTR_CODE_FORMAT)

    @property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""

        if not self._device.get("malfunction"):

            if self._device.get("state") == ADCLock.DeviceState.LOCKED:
                return True

            if self._device.get("state") == ADCLock.DeviceState.UNLOCKED:
                return False

        return None

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        if self._validate_code(kwargs.get("code")):
            try:
                await self.async_lock_callback()
            except PermissionError:
                self._show_permission_error("lock")

            await self._controller.async_coordinator_update()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        if self._validate_code(kwargs.get("code")):
            try:
                await self.async_unlock_callback()
            except PermissionError:
                self._show_permission_error("unlock")

            await self._controller.async_coordinator_update()

    def _validate_code(self, code: str | None) -> bool:
        """Validate given code."""
        check: bool = self._arm_code in [None, ""] or code == self._arm_code
        if not check:
            log.warning("Wrong code entered")
        return check
