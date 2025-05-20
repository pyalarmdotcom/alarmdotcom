"""Interfaces with Alarm.com alarm control panels."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Coroutine, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic

import pyalarmdotcomajax as pyadc
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import InvalidStateError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from pyalarmdotcomajax.controllers.partitions import PartitionController

from .const import (
    CONF_ARM_AWAY,
    CONF_ARM_CODE,
    CONF_ARM_HOME,
    CONF_ARM_NIGHT,
    CONF_FORCE_BYPASS,
    CONF_NO_ENTRY_DELAY,
    CONF_SILENT_ARM,
    DATA_HUB,
    DOMAIN,
)
from .entity import AdcControllerT, AdcEntity, AdcEntityDescription, AdcManagedDeviceT
from .util import cleanup_orphaned_entities_and_devices

if TYPE_CHECKING:
    from .hub import AlarmHub

log = logging.getLogger(__name__)

DISARM = "disarm"
ARM_AWAY = "arm_away"
ARM_STAY = "arm_stay"
ARM_NIGHT = "arm_night"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the light platform."""

    hub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id][DATA_HUB]

    entities = [
        AdcAlarmControlPanelEntity(
            hub=hub, resource_id=device.id, description=entity_description
        )
        for entity_description in ENTITY_DESCRIPTIONS
        for device in hub.api.partitions
        if entity_description.supported_fn(hub, device.id)
    ]
    async_add_entities(entities)

    current_entity_ids = {entity.entity_id for entity in entities}
    current_unique_ids = {
        uid for uid in (entity.unique_id for entity in entities) if uid is not None
    }
    await cleanup_orphaned_entities_and_devices(
        hass,
        config_entry,
        current_entity_ids,
        current_unique_ids,
        "alarm_control_panel",
    )


@callback
def code_format_fn(hub: AlarmHub) -> CodeFormat | None:
    """Return the code format for the device."""

    arm_code = hub.config_entry.options.get(CONF_ARM_CODE)
    if arm_code in [None, ""]:
        return None
    return CodeFormat.NUMBER if re.fullmatch(r"\d+", str(arm_code)) else CodeFormat.TEXT


@callback
def extra_state_attributes(hub: AlarmHub, partition_id: str) -> Mapping[str, Any]:
    """Collect extra state attributes."""

    resource = hub.api.partitions[partition_id]

    return {
        "uncleared_issues": resource.attributes.needs_clear_issues_prompt,
    }


@callback
def state_fn(hub: AlarmHub, partition_id: str) -> AlarmControlPanelState | None:
    """Return the state of a partition."""

    resource = hub.api.partitions[partition_id]

    if resource.attributes.is_malfunctioning:
        return None

    # Mapping of PartitionState to AlarmControlPanelState
    state_mapping = {
        pyadc.partition.PartitionState.DISARMED: AlarmControlPanelState.DISARMED,
        pyadc.partition.PartitionState.ARMED_STAY: AlarmControlPanelState.ARMED_HOME,
        pyadc.partition.PartitionState.ARMED_AWAY: AlarmControlPanelState.ARMED_AWAY,
        pyadc.partition.PartitionState.ARMED_NIGHT: AlarmControlPanelState.ARMED_NIGHT,
    }

    if resource.attributes.state == resource.attributes.desired_state:
        return state_mapping.get(resource.attributes.state)

    desired_state_mapping = {
        pyadc.partition.PartitionState.DISARMED: AlarmControlPanelState.DISARMING,
        pyadc.partition.PartitionState.ARMED_STAY: AlarmControlPanelState.ARMING,
        pyadc.partition.PartitionState.ARMED_AWAY: AlarmControlPanelState.ARMING,
        pyadc.partition.PartitionState.ARMED_NIGHT: AlarmControlPanelState.ARMING,
    }

    return (
        desired_state_mapping.get(resource.attributes.desired_state)
        if resource.attributes.desired_state
        else None
    )


@callback
def supported_features_fn(
    controller: PartitionController, partition_id: str
) -> AlarmControlPanelEntityFeature:
    """Return the supported features for the device."""

    resource = controller.get(partition_id)

    if not resource:
        return AlarmControlPanelEntityFeature(0)

    return (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | (
            AlarmControlPanelEntityFeature.ARM_NIGHT
            if resource.attributes.supports_night_arming
            else 0
        )
    )


@callback
async def control_fn(
    hub: AlarmHub,
    controller: pyadc.PartitionController,
    partition_id: str,
    command: str,
    options: dict[str, Any],
) -> None:
    """Arm/disarm the device."""

    config_options = hub.config_entry.options
    arm_code = config_options.get(CONF_ARM_CODE)

    user_entered_code = options.get("code")

    if user_entered_code != arm_code and arm_code not in [None, ""]:
        raise ServiceValidationError("Invalid code.")

    try:
        if command == DISARM:
            await controller.disarm(partition_id)

        elif command == ARM_AWAY:
            cmd_options = options.get(CONF_ARM_AWAY, {})
            await controller.arm_away(
                partition_id,
                force_bypass=CONF_FORCE_BYPASS in cmd_options,
                no_entry_delay=CONF_NO_ENTRY_DELAY in cmd_options,
            )

        elif command == ARM_STAY:
            cmd_options = options.get(CONF_ARM_HOME, {})
            await controller.arm_stay(
                partition_id,
                force_bypass=CONF_FORCE_BYPASS in cmd_options,
                no_entry_delay=CONF_NO_ENTRY_DELAY in cmd_options,
                silent_arming=CONF_SILENT_ARM in cmd_options,
            )

        elif command == ARM_NIGHT:
            cmd_options = options.get(CONF_ARM_NIGHT, {})
            await controller.arm_night(
                partition_id,
                force_bypass=CONF_FORCE_BYPASS in cmd_options,
                no_entry_delay=CONF_NO_ENTRY_DELAY in cmd_options,
            )

        else:
            raise ServiceValidationError("Unsupported command.")

    except (pyadc.ServiceUnavailable, pyadc.UnexpectedResponse) as err:
        raise InvalidStateError("Failed to disarm partition.") from err


@dataclass(frozen=True, kw_only=True)
class AdcAlarmControlPanelEntityDescription(
    Generic[AdcManagedDeviceT, AdcControllerT],
    AdcEntityDescription[AdcManagedDeviceT, AdcControllerT],
    AlarmControlPanelEntityDescription,
):
    """Base Alarm.com entity description."""

    # fmt: off
    code_format_fn: Callable[[AlarmHub], CodeFormat | None]
    """Return the code format for the device."""
    supported_features_fn: Callable[[AdcControllerT, str], AlarmControlPanelEntityFeature]
    """Return the supported features for the device."""
    control_fn: Callable[[AlarmHub, AdcControllerT, str, str, dict[str, Any]], Coroutine[Any, Any, None]]
    # Hub, Controller, Device ID, Command, Options
    """Arm/disarm the device."""
    state_fn: Callable[[AlarmHub, str], AlarmControlPanelState | None]
    """Return the state of the device."""
    # fmt: on


ENTITY_DESCRIPTIONS: list[AdcAlarmControlPanelEntityDescription] = [
    AdcAlarmControlPanelEntityDescription[
        pyadc.partition.Partition, pyadc.PartitionController
    ](
        key="partitions",
        controller_fn=lambda hub, _: hub.api.partitions,
        state_fn=state_fn,
        code_format_fn=code_format_fn,
        supported_features_fn=supported_features_fn,
        control_fn=control_fn,
    )
]


class AdcAlarmControlPanelEntity(
    AdcEntity[AdcManagedDeviceT, AdcControllerT], AlarmControlPanelEntity
):
    """Base Alarm.com alarm control panel entity."""

    entity_description: AdcAlarmControlPanelEntityDescription

    def _validate_code(self, code: str | None) -> bool:
        arm_code = (
            self.hub.config_entry.options.get("arm_code")
            if hasattr(self.hub, "config_entry")
            else None
        )
        if arm_code in [None, ""] or code == arm_code:
            return True
        log.warning("Wrong code entered for alarm control panel %s.", self.resource_id)
        return False

    @callback
    def initiate_state(self) -> None:
        """Initiate entity state."""

        self._attr_code_format = self.entity_description.code_format_fn(self.hub)
        self._attr_supported_features = self.entity_description.supported_features_fn(
            self.controller, self.resource_id
        )
        self._attr_code_format = self.entity_description.code_format_fn(self.hub)

        super().initiate_state()

    @callback
    def update_state(self, message: pyadc.EventBrokerMessage | None = None) -> None:
        """Update entity state."""

        if isinstance(message, pyadc.ResourceEventMessage):
            self.alarm_state = self.entity_description.state_fn(
                self.hub, self.resource_id
            )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""

        if self._validate_code(code):
            await self.entity_description.control_fn(
                self.hub, self.controller, self.resource_id, DISARM, {"code": code}
            )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""

        if self._validate_code(code):
            await self.entity_description.control_fn(
                self.hub, self.controller, self.resource_id, ARM_STAY, {"code": code}
            )

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""

        if self._validate_code(code):
            await self.entity_description.control_fn(
                self.hub, self.controller, self.resource_id, ARM_AWAY, {"code": code}
            )

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""

        if self._validate_code(code):
            await self.entity_description.control_fn(
                self.hub, self.controller, self.resource_id, ARM_NIGHT, {"code": code}
            )
