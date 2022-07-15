"""Interfaces with Alarm.com alarm control panels."""
from __future__ import annotations

import logging
import re

from homeassistant import config_entries
from homeassistant import core
from homeassistant.components import persistent_notification
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature
from homeassistant.components.alarm_control_panel import CodeFormat
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ALARM_ARMED_AWAY
from homeassistant.const import STATE_ALARM_ARMED_HOME
from homeassistant.const import STATE_ALARM_ARMED_NIGHT
from homeassistant.const import STATE_ALARM_ARMING
from homeassistant.const import STATE_ALARM_DISARMED
from homeassistant.const import STATE_ALARM_DISARMING
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from homeassistant.helpers.typing import ConfigType
from pyalarmdotcomajax.devices import BaseDevice as libBaseDevice
from pyalarmdotcomajax.devices.partition import Partition as libPartition

from .alarmhub import AlarmHub
from .base_device import HardwareBaseDevice
from .const import CONF_ARM_AWAY
from .const import CONF_ARM_CODE
from .const import CONF_ARM_HOME
from .const import CONF_ARM_NIGHT
from .const import DOMAIN
from .const import MIGRATE_MSG_ALERT

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

    alarmhub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        AlarmControlPanel(
            alarmhub=alarmhub,
            device=device,
        )
        for device in alarmhub.system.partitions
    )


class AlarmControlPanel(HardwareBaseDevice, AlarmControlPanelEntity):  # type: ignore
    """Alarm.com Alarm Control Panel entity."""

    device_type_name: str = "Alarm Control Panel"
    _device: libPartition

    def __init__(
        self,
        alarmhub: AlarmHub,
        device: libBaseDevice,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""

        super().__init__(alarmhub, device, device.system_id)

        self._attr_code_format = (
            (
                CodeFormat.NUMBER
                if (isinstance(arm_code, str) and re.search("^\\d+$", arm_code))
                else CodeFormat.TEXT
            )
            if (arm_code := alarmhub.options.get(CONF_ARM_CODE))
            else None
        )

        self._attr_supported_features = int(
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_NIGHT
        )

    @callback  # type: ignore
    def update_device_data(self) -> None:
        """Update the entity when coordinator is updated."""

        self._attr_state = self._determine_state(self._device.state)

        self._attr_extra_state_attributes.update(
            {
                "desired_state": self._device.desired_state.name.title()
                if isinstance(
                    self._device.desired_state,
                    libPartition.DeviceState,
                )
                else None,
                "uncleared_issues": self._device.uncleared_issues,
            }
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if self._validate_code(code):

            self._attr_state = STATE_ALARM_DISARMING

            try:
                await self._device.async_disarm()
            except PermissionError:
                self._show_permission_error("disarm")

            await self._alarmhub.coordinator.async_refresh()

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""

        arm_profile = self._alarmhub.options.get(CONF_ARM_NIGHT, {})

        if self._validate_code(code):

            self._attr_state = STATE_ALARM_ARMING

            try:
                await self._device.async_arm_night(
                    force_bypass="bypass" in arm_profile,
                    no_entry_delay="delay" not in arm_profile,
                    silent_arming="silent" in arm_profile,
                )
            except PermissionError:
                self._show_permission_error("arm_night")

            await self._alarmhub.coordinator.async_refresh()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""

        arm_profile = self._alarmhub.options.get(CONF_ARM_HOME, {})

        if self._validate_code(code):

            self._attr_state = STATE_ALARM_ARMING

            try:
                await self._device.async_arm_stay(
                    force_bypass="bypass" in arm_profile,
                    no_entry_delay="delay" not in arm_profile,
                    silent_arming="silent" in arm_profile,
                )
            except PermissionError:
                self._show_permission_error("arm_home")

            await self._alarmhub.coordinator.async_refresh()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""

        arm_profile = self._alarmhub.options.get(CONF_ARM_AWAY, {})

        if self._validate_code(code):

            self._attr_state = STATE_ALARM_ARMING

            try:
                await self._device.async_arm_away(
                    force_bypass="bypass" in arm_profile,
                    no_entry_delay="delay" not in arm_profile,
                    silent_arming="silent" in arm_profile,
                )
            except PermissionError:
                self._show_permission_error("arm_away")

            await self._alarmhub.coordinator.async_refresh()

    #
    # Helpers
    #

    def _determine_state(self, state: libPartition.DeviceState) -> str | None:
        """Return the state of the device."""

        log.debug("Processing state %s for %s", state, self.name)

        if not self._device.malfunction:

            if state == libPartition.DeviceState.DISARMED:
                return str(STATE_ALARM_DISARMED)
            if state == libPartition.DeviceState.ARMED_STAY:
                return str(STATE_ALARM_ARMED_HOME)
            if state == libPartition.DeviceState.ARMED_AWAY:
                return str(STATE_ALARM_ARMED_AWAY)
            if state == libPartition.DeviceState.ARMED_NIGHT:
                return str(STATE_ALARM_ARMED_NIGHT)

            log.error(
                "Cannot determine state. Found raw state of %s.",
                state,
            )

        return None

    def _validate_code(self, code: str | None) -> bool | str:
        """Validate given code."""
        check: bool | str = (arm_code := self._alarmhub.options.get(CONF_ARM_CODE)) in [
            None,
            "",
        ] or code == arm_code
        if not check:
            log.warning("Wrong code entered.")
        return check
