"""Alarm.com controller for WaterValves."""

import logging
from enum import StrEnum
from types import MappingProxyType

from _pyalarmdotcomajax.adc.util import Param_Id, cli_action
from _pyalarmdotcomajax.controllers.base import BaseController, device_controller
from _pyalarmdotcomajax.exceptions import UnsupportedOperation
from _pyalarmdotcomajax.models.base import ResourceType
from _pyalarmdotcomajax.models.water_valve import WaterValve, WaterValveState
from _pyalarmdotcomajax.websocket.client import SupportedResourceEvents, WebSocketState
from _pyalarmdotcomajax.websocket.messages import ResourceEventType

log = logging.getLogger(__name__)


class WaterValveCommand(StrEnum):
    """Commands for ADC WaterValves."""

    OPEN = "open"
    CLOSE = "close"


STATE_COMMAND_MAP = {
    WaterValveState.OPEN: WaterValveCommand.OPEN,
    WaterValveState.CLOSED: WaterValveCommand.CLOSE,
}


@device_controller(ResourceType.WATER_VALVE, WaterValve)
class WaterValveController(BaseController[WaterValve]):
    """Controller for water valves."""

    # Water valves are fetched directly and are outside the first connection's catalog reconciliation.
    _refresh_connection_states = frozenset({WebSocketState.CONNECTED, WebSocketState.RECONNECTED})
    _event_state_map = MappingProxyType(
        {
            ResourceEventType.Opened: WaterValveState.OPEN,
            ResourceEventType.Closed: WaterValveState.CLOSED,
        }
    )
    _supported_resource_events = SupportedResourceEvents(
        events=[*_event_state_map.keys()]
    )

    @cli_action()
    async def open(self, id: Param_Id) -> None:
        """Open a water valve."""
        await self.set_state(id, state=WaterValveState.OPEN)

    @cli_action()
    async def close(self, id: Param_Id) -> None:
        """Close a water valve."""
        await self.set_state(id, state=WaterValveState.CLOSED)

    async def set_state(self, id: str, state: WaterValveState) -> None:
        """Change water valve state."""
        if not (command := STATE_COMMAND_MAP.get(state)):
            raise UnsupportedOperation(f"State {state} not implemented.")
        await self._send_command(id, command)
