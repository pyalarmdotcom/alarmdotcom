"""Alarm.com controller for sensors."""

import asyncio
import logging
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from _pyalarmdotcomajax.const import ATTR_DESIRED_STATE, ATTR_STATE
from _pyalarmdotcomajax.controllers.base import BaseController, device_controller
from _pyalarmdotcomajax.models.base import ResourceType
from _pyalarmdotcomajax.models.jsonapi import Resource
from _pyalarmdotcomajax.models.sensor import Sensor, SensorState, SensorSubtype
from _pyalarmdotcomajax.websocket.client import SupportedResourceEvents
from _pyalarmdotcomajax.websocket.messages import (
    BaseWSMessage,
    EventWSMessage,
    ResourceEventType,
)

if TYPE_CHECKING:
    from _pyalarmdotcomajax.models import AdcResourceT

log = logging.getLogger(__name__)


# Alarm.com collapses a quick open-then-close into a single OpenedClosed event
# (type 100) instead of an Opened followed by a Closed. Writing its literal
# SensorState.OPENED_CLOSED (9) left the sensor reading *closed* downstream -
# Home Assistant derives on/off from state parity and 9 is odd - so a real
# door opening produced no state change at all: nothing in history, nothing an
# automation could trigger on, and the sensor sat on a value no later event
# was guaranteed to clear. It is mapped to the state the event actually
# reports (open / active) and settled back a moment later by
# _schedule_opened_closed_settle, replaying the open-then-close that happened.
MOTION_EVENT_STATE_MAP = {
    ResourceEventType.Closed: SensorState.IDLE,
    ResourceEventType.DoorLeftOpenRestoral: SensorState.IDLE,
    ResourceEventType.OpenedClosed: SensorState.ACTIVE,
    ResourceEventType.Opened: SensorState.ACTIVE,
}
SENSOR_EVENT_STATE_MAP = {
    ResourceEventType.Closed: SensorState.CLOSED,
    ResourceEventType.DoorLeftOpenRestoral: SensorState.CLOSED,
    ResourceEventType.OpenedClosed: SensorState.OPEN,
    ResourceEventType.Opened: SensorState.OPEN,
}

# How long the momentary open stays visible before settling back to closed.
# Long enough for Home Assistant to record a distinct state change (and for an
# automation to see it), short enough to stay honest about a door that is
# already shut.
OPENED_CLOSED_PULSE_S = 2.0


# Derived from the state map, as in every other device controller, so the
# subscription list and the state map can no longer drift apart.
SUPPORTED_RESOURCE_EVENTS = SupportedResourceEvents(
    events=[
        ResourceEventType.Bypassed,
        ResourceEventType.EndOfBypass,
        *SENSOR_EVENT_STATE_MAP.keys(),
    ]
)


@device_controller(ResourceType.SENSOR, Sensor)
class SensorController(BaseController[Sensor]):
    """Controller for sensors."""

    # Contact-sensor mapping is the class-level default, so state updates go
    # through the same unguarded path every other device controller uses
    # (BaseController._base_handle_event). Motion sensors need IDLE/ACTIVE
    # rather than CLOSED/OPEN, which a ClassVar cannot express per device, so
    # _handle_event below corrects them.
    _event_state_map = MappingProxyType(SENSOR_EVENT_STATE_MAP)
    _supported_resource_events = SUPPORTED_RESOURCE_EVENTS

    # Declared on the class, not only created in __init__, so that the pulse
    # bookkeeping is visible to anything inspecting the controller's interface.
    _opened_closed_pulses: dict[str, asyncio.Task] | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the controller and its pulse bookkeeping."""
        super().__init__(*args, **kwargs)

        self._opened_closed_pulses = {}

    async def _handle_event(
        self, adc_resource: "AdcResourceT", message: BaseWSMessage
    ) -> "AdcResourceT":
        """Handle light-specific WebSocket events."""

        # Contact-sensor state is carried entirely by `subtype` (Opened /
        # Closed / OpenedClosed). `event_value` means nothing for these events
        # and is not read anywhere below, but gating on it dropped every state
        # update whenever Alarm.com sent the event without one.
        if isinstance(message, EventWSMessage) and isinstance(adc_resource, Sensor):
            #
            # STATE UPDATES
            #

            state: SensorState | None = None

            match message.subtype:
                case ResourceEventType.Closed:
                    state = (
                        SensorState.IDLE
                        if adc_resource.subtype == SensorSubtype.MOTION_SENSOR
                        else SensorState.CLOSED
                    )
                case ResourceEventType.Opened:
                    state = (
                        SensorState.ACTIVE
                        if adc_resource.subtype == SensorSubtype.MOTION_SENSOR
                        else SensorState.OPEN
                    )
                case ResourceEventType.OpenedClosed:
                    state = (
                        SensorState.ACTIVE
                        if adc_resource.subtype == SensorSubtype.MOTION_SENSOR
                        else SensorState.OPEN
                    )
                case ResourceEventType.DoorLeftOpenRestoral:
                    state = SensorState.CLOSED

            # Preserve our glass-break restoral handling from #111.
            if (
                state == SensorState.CLOSED
                and adc_resource.subtype in (
                    SensorSubtype.GLASS_BREAK_DETECTOR,
                    SensorSubtype.PANEL_GLASS_BREAK_DETECTOR,
                )
            ):
                state = SensorState.IDLE

            if state:
                # Any newer event supersedes a pulse still waiting to settle -
                # without this, an OpenedClosed immediately followed by a real
                # Opened would be closed again by the older pulse's timer and
                # the sensor would read closed while the door stood open.
                self._cancel_opened_closed_settle(adc_resource.id)

                adc_resource.api_resource.attributes.update(
                    {
                        ATTR_STATE: state.value,
                        ATTR_DESIRED_STATE: state.value,
                    }
                )

                if message.subtype == ResourceEventType.OpenedClosed:
                    self._schedule_opened_closed_settle(
                        adc_resource.id,
                        SensorState.IDLE
                        if adc_resource.subtype == SensorSubtype.MOTION_SENSOR
                        else SensorState.CLOSED,
                        adc_resource.api_resource,
                    )
                    # The settle assumes the sensor ended closed. Ask Alarm.com once the pulse has played out,
                    # so a sensor that was reopened (or never closed) does not sit on an assumed state.
                    self._request_reconcile("opened/closed event")

            #
            # BYPASS UPDATES
            #

            if message.subtype in [
                ResourceEventType.Bypassed,
                ResourceEventType.EndOfBypass,
            ]:
                adc_resource.api_resource.attributes.update(
                    {
                        "isBypassed": message.subtype == ResourceEventType.Bypassed,
                    }
                )

        return adc_resource

    #######################
    # OPENED/CLOSED PULSE #
    #######################

    def _cancel_opened_closed_settle(self, resource_id: str) -> None:
        """Drop any pulse still waiting to settle this sensor."""
        if not self._opened_closed_pulses:
            return

        if task := self._opened_closed_pulses.pop(resource_id, None):
            task.cancel()

    def _schedule_opened_closed_settle(
        self, resource_id: str, settled_state: SensorState, opened: Resource
    ) -> None:
        """Settle a momentary open back to closed after the pulse elapses."""
        if self._opened_closed_pulses is None:
            return

        task = asyncio.create_task(
            self._settle_opened_closed(resource_id, settled_state, opened)
        )
        # Tracked alongside the controller's other background work, so a pulse
        # in flight is at least visible to anything inspecting the controller.
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        self._opened_closed_pulses[resource_id] = task

        def _forget(finished: asyncio.Task) -> None:
            """Drop the finished task, unless a newer pulse already replaced it."""
            pulses = self._opened_closed_pulses

            if pulses is not None and pulses.get(resource_id) is finished:
                del pulses[resource_id]

        task.add_done_callback(_forget)

    async def _settle_opened_closed(
        self, resource_id: str, settled_state: SensorState, opened: Resource
    ) -> None:
        """Write the closed half of an OpenedClosed event and publish it."""
        await asyncio.sleep(OPENED_CLOSED_PULSE_S)

        adc_resource = self.get(resource_id)

        if adc_resource is None:
            return

        # Only settle the open this pulse itself wrote. Registering an event
        # re-wraps the same underlying Resource, so identity still holds across
        # our own update - but a refresh builds a new one from the API payload,
        # and that newer truth wins even when it happens to say "open" too.
        # Without this check a refresh landing inside the pulse window would be
        # overwritten by a timer that no longer speaks for the device.
        if adc_resource.api_resource is not opened:
            return

        if adc_resource.attributes.state not in (SensorState.OPEN, SensorState.ACTIVE):
            return

        adc_resource.api_resource.attributes.update(
            {
                ATTR_STATE: settled_state.value,
                ATTR_DESIRED_STATE: settled_state.value,
            }
        )

        await self._register_or_update_resource(adc_resource.api_resource)
