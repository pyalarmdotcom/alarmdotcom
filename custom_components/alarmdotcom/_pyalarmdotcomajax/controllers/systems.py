"""Alarm.com controller for systems."""

import logging
from typing import Annotated

import typer
from _pyalarmdotcomajax.adc.util import Param_Id, cli_action
from _pyalarmdotcomajax.controllers.base import BaseController
from _pyalarmdotcomajax.models.base import ResourceType
from _pyalarmdotcomajax.models.system import System

from .base import device_controller

log = logging.getLogger(__name__)


@device_controller(ResourceType.SYSTEM, System)
class SystemController(BaseController[System]):
    """Controller for systems."""

    @cli_action()
    async def stop_alarms(self, id: Param_Id) -> None:
        """Stop all alarms and disarm a system."""

        await self._send_command(id, "stopAlarms")

    @cli_action()
    async def clear_smoke_sensor(
        self,
        system_id: Annotated[
            str,
            typer.Argument(help="ID of the system to which the smoke system belongs."),
        ],
        smoke_sensor_id: Annotated[
            str, typer.Argument(help="ID of the smoke sensor to be cleared.")
        ],
    ) -> None:
        """Change status of a smoke sensor to closed."""

        await self._send_command(
            system_id, "clearSmokeSensorStatus", {"data": smoke_sensor_id}
        )

    @cli_action()
    async def clear_alarms_in_memory(
        self,
        system_id: Annotated[
            str, typer.Argument(help="ID of the system on which to clear alarms.")
        ],
    ) -> None:
        """Clear alarms in memory on a system."""

        await self._send_command(system_id, "clearAlarmsInMemoryTrouble")
