"""Alarm.com controller for partitions."""

# ruff: noqa: FBT002

import logging
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any

import typer
from _pyalarmdotcomajax.adc.util import Param_Id, cli_action
from _pyalarmdotcomajax.controllers.base import BaseController, device_controller
from _pyalarmdotcomajax.exceptions import UnsupportedOperation
from _pyalarmdotcomajax.models.base import ResourceType
from _pyalarmdotcomajax.models.partition import (
    ExtendedArmingOptionItems,
    Partition,
    PartitionState,
)
from _pyalarmdotcomajax.websocket.client import SupportedResourceEvents
from _pyalarmdotcomajax.websocket.messages import ResourceEventType

log = logging.getLogger(__name__)

ARMOPT_BYPASS_SENSORS = "forceBypass"
ARMOPT_NO_ENTRY_DELAY = "noEntryDelay"
ARMOPT_SILENT_ARMING = "silentArming"
ARMOPT_NIGHT_ARMING = "nightArming"
ARMOPT_SELECTIVELY_BYPASS_SENSORS = "selectiveBypass"
ARMOPT_FORCE_ARM = "forceArm"


class PartitionCommand(StrEnum):
    """Commands for ADC partitions."""

    DISARM = "disarm"
    ARM_STAY = "armStay"
    ARM_AWAY = "armAway"


STATE_COMMAND_MAP = {
    PartitionState.DISARMED: PartitionCommand.DISARM,
    PartitionState.ARMED_STAY: PartitionCommand.ARM_STAY,
    PartitionState.ARMED_AWAY: PartitionCommand.ARM_AWAY,
    PartitionState.ARMED_NIGHT: PartitionCommand.ARM_STAY,  # Armed Night is Arm Stay with Night Arming extended option.
}

ARMING_EXTENSION_BODY_MAP = {
    ExtendedArmingOptionItems.BYPASS_SENSORS: ARMOPT_BYPASS_SENSORS,
    ExtendedArmingOptionItems.NO_ENTRY_DELAY: ARMOPT_NO_ENTRY_DELAY,
    ExtendedArmingOptionItems.SILENT_ARMING: ARMOPT_SILENT_ARMING,
    ExtendedArmingOptionItems.NIGHT_ARMING: ARMOPT_NIGHT_ARMING,
    ExtendedArmingOptionItems.SELECTIVELY_BYPASS_SENSORS: ARMOPT_SELECTIVELY_BYPASS_SENSORS,
    ExtendedArmingOptionItems.FORCE_ARM: ARMOPT_FORCE_ARM,
}

ARMING_OPTIONS_BODY = {
    ARMOPT_BYPASS_SENSORS: False,
    ARMOPT_NO_ENTRY_DELAY: False,
    ARMOPT_SILENT_ARMING: False,
    ARMOPT_NIGHT_ARMING: False,
    ARMOPT_SELECTIVELY_BYPASS_SENSORS: False,
    ARMOPT_FORCE_ARM: False,
}


# TODO: EventBrokerTopic.Alarm | EventBrokerTopic.PolicePanic:


@device_controller(ResourceType.PARTITION, Partition)
class PartitionController(BaseController[Partition]):
    """Controller for partitions."""

    _event_state_map = MappingProxyType(
        {
            ResourceEventType.Disarmed: PartitionState.DISARMED,
            ResourceEventType.ArmedAway: PartitionState.ARMED_AWAY,
            ResourceEventType.ArmedStay: PartitionState.ARMED_STAY,
            ResourceEventType.ArmedNight: PartitionState.ARMED_NIGHT,
        }
    )
    _supported_resource_events = SupportedResourceEvents(events=[*_event_state_map.keys()])

    # Special handling of 422 status.
    # 422 sometimes occurs when forceBypass is True but there's nothing to bypass.

    def get_device_partition(self, resource_id: str) -> str | None:
        """Get the partition to which a device belongs."""

        for partition in self.items:
            if resource_id in partition.items:
                return partition.id

        return None

    @cli_action()
    async def clear_faults(self, id: Param_Id) -> None:
        """Clear all faults on a partition."""

        await self._send_command(id, "clearIssues")

    @cli_action()
    async def disarm(self, id: Param_Id) -> None:
        """Disarm a partition."""

        await self.set_state(id, PartitionState.DISARMED)

    @cli_action()
    async def arm_stay(
        self,
        id: Param_Id,
        force_bypass: Annotated[
            bool,
            typer.Option(help="Bypass all open zones before arming.", show_default=False),
        ] = False,
        no_entry_delay: Annotated[
            bool,
            typer.Option(
                help="Bypass entry delay. This will sound the alarm immediately when an entry zone triggers.",
                show_default=False,
            ),
        ] = False,
        silent_arming: Annotated[
            bool,
            typer.Option(
                help="Arm the system without emitting arming \\ exit delay tones at the panel.",
                show_default=False,
            ),
        ] = False,
    ) -> None:
        """Arm a partition in stay mode."""

        extended_arming_options: list[ExtendedArmingOptionItems | None] = [
            ExtendedArmingOptionItems.BYPASS_SENSORS if force_bypass else None,
            ExtendedArmingOptionItems.NO_ENTRY_DELAY if no_entry_delay else None,
            ExtendedArmingOptionItems.SILENT_ARMING if silent_arming else None,
        ]

        await self.set_state(
            id,
            PartitionState.ARMED_STAY,
            [option for option in extended_arming_options if option is not None],
        )

    @cli_action()
    async def arm_away(
        self,
        id: Param_Id,
        force_bypass: Annotated[
            bool,
            typer.Option(help="Bypass all open zones before arming.", show_default=False),
        ] = False,
        no_entry_delay: Annotated[
            bool,
            typer.Option(
                help="Bypass entry delay. This will sound the alarm immediately when an entry zone triggers.",
                show_default=False,
            ),
        ] = False,
        silent_arming: Annotated[
            bool,
            typer.Option(
                help="Arm the system without emitting arming \\ exit delay tones at the panel.",
                show_default=False,
            ),
        ] = False,
    ) -> None:
        """Arm a partition in away mode."""

        extended_arming_options: list[ExtendedArmingOptionItems | None] = [
            ExtendedArmingOptionItems.BYPASS_SENSORS if force_bypass else None,
            ExtendedArmingOptionItems.NO_ENTRY_DELAY if no_entry_delay else None,
            ExtendedArmingOptionItems.SILENT_ARMING if silent_arming else None,
        ]

        await self.set_state(
            id,
            PartitionState.ARMED_AWAY,
            [option for option in extended_arming_options if option is not None],
        )

    @cli_action()
    async def arm_night(
        self,
        id: Param_Id,
        force_bypass: Annotated[
            bool,
            typer.Option(help="Bypass all open zones before arming.", show_default=False),
        ] = False,
        no_entry_delay: Annotated[
            bool,
            typer.Option(
                help="Bypass entry delay. This will sound the alarm immediately when an entry zone triggers.",
                show_default=False,
            ),
        ] = False,
        silent_arming: Annotated[
            bool,
            typer.Option(
                help="Arm the system without emitting arming \\ exit delay tones at the panel.",
                show_default=False,
            ),
        ] = False,
    ) -> None:
        """Arm a partition in night mode."""

        extended_arming_options: list[ExtendedArmingOptionItems | None] = [
            ExtendedArmingOptionItems.BYPASS_SENSORS if force_bypass else None,
            ExtendedArmingOptionItems.NO_ENTRY_DELAY if no_entry_delay else None,
            ExtendedArmingOptionItems.SILENT_ARMING if silent_arming else None,
            ExtendedArmingOptionItems.NIGHT_ARMING,
        ]

        await self.set_state(
            id,
            PartitionState.ARMED_NIGHT,
            [option for option in extended_arming_options if option is not None],
        )

    async def set_state(
        self,
        id: str,
        state: PartitionState,
        extended_arming_options: list[ExtendedArmingOptionItems] | None = None,
    ) -> None:
        """Change partition state."""

        msg_body: dict[str, Any] = ARMING_OPTIONS_BODY.copy()

        extended_arming_options = extended_arming_options or []

        # Disarm does not support extended arming options.
        if state == PartitionState.DISARMED and extended_arming_options:
            raise UnsupportedOperation("Extended arming options not supported for disarm.")

        # Add extended arming options to body.
        # Check that each requested arming option is supported for the partition.
        # Always permit force bypass. Not sure if this is right but it seems to work.

        supported_options = getattr(self[id].attributes.extended_arming_options, state.name.lower()) or []
        flattened_supported_options: list[ExtendedArmingOptionItems] = []
        for supported_option in supported_options:
            if isinstance(supported_option, list):
                flattened_supported_options.extend(supported_option)
            else:
                flattened_supported_options.append(supported_option)

        for option in extended_arming_options:
            if option in flattened_supported_options or (
                option == ExtendedArmingOptionItems.BYPASS_SENSORS and ARMING_EXTENSION_BODY_MAP.get(option)
            ):
                msg_body.update({ARMING_EXTENSION_BODY_MAP[option]: True})
            else:
                raise UnsupportedOperation(f"Extended arming option {option} not supported for {state}.")

        if not (command := STATE_COMMAND_MAP.get(state)):
            raise UnsupportedOperation(f"State {state} not implemented.")

        await self._send_command(id, command.value, msg_body)

    @cli_action()
    async def change_sensor_bypass(
        self,
        partition_id: Param_Id,
        bypass_ids: Annotated[
            list[str] | None,
            typer.Option(help="List of sensors to bypass.", show_default=True),
        ] = None,
        unbypass_ids: Annotated[
            list[str] | None,
            typer.Option(help="List of sensors to unbypass.", show_default=True),
        ] = None,
    ) -> None:
        """Bypass or unbypass sensors on a partition."""

        if not (bypass_ids or unbypass_ids):
            raise ValueError("Either bypass_ids or unbypass_ids must be provided.")

        await self._send_command(
            partition_id,
            "bypassSensors",
            {
                "bypass": "|".join(bypass_ids) if bypass_ids else "",
                "unbypass": "|".join(unbypass_ids) if unbypass_ids else "",
            },
        )
