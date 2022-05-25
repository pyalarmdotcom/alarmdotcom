"""Interfaces with Alarm.com alarm control panels."""
from __future__ import annotations

from collections.abc import Callable
from enum import Enum
import logging
import re
from types import MappingProxyType
from typing import Any

from homeassistant import config_entries
from homeassistant import core
from homeassistant.components import alarm_control_panel
from homeassistant.components import persistent_notification
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ALARM_ARMED_AWAY
from homeassistant.const import STATE_ALARM_ARMED_HOME
from homeassistant.const import STATE_ALARM_ARMED_NIGHT
from homeassistant.const import STATE_ALARM_DISARMED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyalarmdotcomajax.devices import Partition as pyadcPartition
from typing_extensions import NotRequired

from .base_device import IntBaseDevice
from .const import CONF_ARM_AWAY
from .const import CONF_ARM_CODE
from .const import CONF_ARM_HOME
from .const import CONF_ARM_NIGHT
from .const import DOMAIN
from .const import MIGRATE_MSG_ALERT
from .const import STATE_MALFUNCTION

log = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,  # pylint: disable=unused-argument
    discovery_info: DiscoveryInfoType | None = None,  # pylint: disable=unused-argument
) -> None:
    """Set up the legacy platform."""

    log.debug(
        "Alarmdotcom: Detected legacy platform config entry. Converting to Home"
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
    discovery_info: DiscoveryInfoType | None = None,  # pylint: disable=unused-argument
) -> None:
    """Set up the sensor platform and create a master device."""

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        IntAlarmControlPanel(
            coordinator=coordinator,
            device_data=coordinator.data.get("entity_data", {}).get(device_id),
            config_options=config_entry.options,
        )
        for device_id in coordinator.data.get("partition_ids", [])
    )


class IntAlarmControlPanel(IntBaseDevice, AlarmControlPanelEntity):  # type: ignore
    """Alarm.com Alarm Control Panel entity."""

    device_type_name: str = "Alarm Control Panel"

    # class PartitionState(Enum):
    #     """Enum of arming states."""

    #     UNKNOWN = "UNKNOWN"
    #     DISARMED = "DISARMED"
    #     ARMED_STAY = "ARMED_STAY"
    #     ARMED_AWAY = "ARMED_AWAY"
    #     ARMED_NIGHT = "ARMED_NIGHT"
    class DataStructure(IntBaseDevice.DataStructure):
        """Dict for an ADCI partition."""

        uncleared_issues: bool
        desired_state: Enum
        raw_state_text: str
        system_id: NotRequired[str]
        state: pyadcPartition.DeviceState
        parent_id: str
        read_only: bool

        async_disarm_callback: Callable
        async_arm_home_callback: Callable
        async_arm_away_callback: Callable
        async_arm_night_callback: Callable

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_data: DataStructure,
        config_options: MappingProxyType[str, Any],
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""

        super().__init__(coordinator, device_data)

        self._device = device_data

        self._arm_code: str | None = config_options.get(CONF_ARM_CODE)
        self._conf_arm_home: set = set(config_options.get(CONF_ARM_HOME, {}))
        self._conf_arm_away: set = set(config_options.get(CONF_ARM_AWAY, {}))
        self._conf_arm_night: set = set(config_options.get(CONF_ARM_NIGHT, {}))

        try:
            self.async_arm_home_callback: Callable = self._device[
                "async_arm_home_callback"
            ]
            self.async_arm_away_callback: Callable = self._device[
                "async_arm_away_callback"
            ]
            self.async_arm_night_callback: Callable = self._device[
                "async_arm_night_callback"
            ]
            self.async_disarm_callback: Callable = self._device["async_disarm_callback"]
        except KeyError:
            log.error("Failed to initialize control functions for %s.", self.unique_id)
            self._attr_available = False

        log.debug(
            "%s: Initializing Alarm.com control panel entity for partition %s.",
            __name__,
            self.unique_id,
        )

    @property
    def code_format(
        self,
    ) -> alarm_control_panel.FORMAT_NUMBER | alarm_control_panel.FORMAT_TEXT | None:
        """Return one or more digits/characters."""
        if self._arm_code in [None, ""]:
            return None
        if isinstance(self._arm_code, str) and re.search("^\\d+$", self._arm_code):
            return alarm_control_panel.FORMAT_NUMBER
        return alarm_control_panel.FORMAT_TEXT

    @property
    def state(self) -> str:
        """Return the state of the device."""

        if self._device.get("state") == pyadcPartition.DeviceState.DISARMED:
            return str(STATE_ALARM_DISARMED)
        if self._device["state"] == pyadcPartition.DeviceState.ARMED_STAY:
            return str(STATE_ALARM_ARMED_HOME)
        if self._device["state"] == pyadcPartition.DeviceState.ARMED_AWAY:
            return str(STATE_ALARM_ARMED_AWAY)
        if self._device["state"] == pyadcPartition.DeviceState.ARMED_NIGHT:
            return str(STATE_ALARM_ARMED_NIGHT)

        return str(STATE_MALFUNCTION)

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""

        desired_state_name = None
        if desired_state := self._device.get("desired_state"):
            desired_state_name = desired_state.name.title()

        return dict(
            (super().extra_state_attributes or {})
            | {
                "desired_state": desired_state_name,
                "uncleared_issues": self._device.get("uncleared_issues"),
            }
        )

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""

        return int(
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_NIGHT
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if self._validate_code(code):
            try:
                await self.async_disarm_callback()
            except PermissionError:
                self._show_permission_error("disarm")

            await self.coordinator.async_update()

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""

        if self._validate_code(code):
            try:
                await self.async_arm_night_callback(
                    force_bypass="bypass" in self._conf_arm_night,
                    no_entry_delay="delay" not in self._conf_arm_night,
                    silent_arming="silent" in self._conf_arm_night,
                )
            except PermissionError:
                self._show_permission_error("arm_night")

            await self.coordinator.async_update()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""

        if self._validate_code(code):
            try:
                await self.async_arm_home_callback(
                    force_bypass="bypass" in self._conf_arm_home,
                    no_entry_delay="delay" not in self._conf_arm_home,
                    silent_arming="silent" in self._conf_arm_home,
                )
            except PermissionError:
                self._show_permission_error("arm_home")

            await self.coordinator.async_update()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if self._validate_code(code):
            try:
                await self.async_arm_away_callback(
                    force_bypass="bypass" in self._conf_arm_away,
                    no_entry_delay="delay" not in self._conf_arm_away,
                    silent_arming="silent" in self._conf_arm_away,
                )
            except PermissionError:
                self._show_permission_error("arm_away")

            await self.coordinator.async_update()

    def _validate_code(self, code: str | None) -> bool | str:
        """Validate given code."""
        check: bool | str = self._arm_code in [None, ""] or code == self._arm_code
        if not check:
            log.warning("Wrong code entered")
        return check
