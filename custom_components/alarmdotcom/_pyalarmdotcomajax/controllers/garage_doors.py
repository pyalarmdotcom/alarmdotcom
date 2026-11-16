"""Alarm.com controller for garage doors."""


import logging
from enum import StrEnum
from types import MappingProxyType

from _pyalarmdotcomajax.adc.util import Param_Id, cli_action
from _pyalarmdotcomajax.controllers.base import BaseController, device_controller
from _pyalarmdotcomajax.exceptions import UnsupportedOperation
from _pyalarmdotcomajax.models.base import ResourceType
from _pyalarmdotcomajax.models.garage_door import GarageDoor, GarageDoorState
from _pyalarmdotcomajax.websocket.client import SupportedResourceEvents
from _pyalarmdotcomajax.websocket.messages import ResourceEventType

log = logging.getLogger(__name__)


class GarageDoorCommand(StrEnum):
    """Commands for ADC garage doors."""

    OPEN = "open"
    CLOSE = "close"


STATE_COMMAND_MAP = {
    GarageDoorState.OPEN: GarageDoorCommand.OPEN,
    GarageDoorState.CLOSED: GarageDoorCommand.CLOSE,
}


@device_controller(ResourceType.GARAGE_DOOR, GarageDoor)
class GarageDoorController(BaseController[GarageDoor]):
    """Controller for managing garage door devices."""

    _event_state_map = MappingProxyType(
        {
            ResourceEventType.Opened: GarageDoorState.OPEN,
            ResourceEventType.Closed: GarageDoorState.CLOSED,
        }
    )
    _supported_resource_events = SupportedResourceEvents(
        events=[*_event_state_map.keys()]
    )

    @cli_action()
    async def open(self, id: Param_Id) -> None:
        """Open a garage door."""
        await self.set_state(id, state=GarageDoorState.OPEN)

    @cli_action()
    async def close(self, id: Param_Id) -> None:
        """Close a garage door."""
        await self.set_state(id, state=GarageDoorState.CLOSED)

    async def set_state(self, id: str, state: GarageDoorState) -> None:
        """Change garage door state."""
        if not (command := STATE_COMMAND_MAP.get(state)):
            raise UnsupportedOperation(f"State {state} not implemented.")
        await self._send_command(id, command)
