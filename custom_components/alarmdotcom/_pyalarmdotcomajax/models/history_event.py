"""
Alarm.com model for activity history events.

This is a genuinely different kind of resource than everything else in
this library models: every other resource represents a device's current,
persistent state (a lock, a sensor, a light), kept up to date live via the
websocket event stream. A history event is a point-in-time record of
something that already happened - it has no ongoing state of its own, and
it does not arrive over the websocket at all. It has to be actively
polled from a separate endpoint (`activity/history-event`, reached via a
day-grouped `activity/activity-day` listing) - see controllers/history_events.py.

Confirmed directly from a real response captured from the Alarm.com web
app's own Activity page (not guessed from other endpoints' conventions,
since this endpoint is entirely undocumented) - see the extensive
comments on individual fields below for what's actually been observed
versus assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import parse_qs

from _pyalarmdotcomajax.models.base import (
    AdcResource,
    AdcResourceAttributes,
    ResourceType,
)


@dataclass(kw_only=True)
class HistoryEventAttributes(AdcResourceAttributes):
    """
    Attributes of a single activity history event.

    Deliberately does not model every field seen in a real captured
    response (thumbnails, SD-card/video-clip-related fields, icon data) -
    those matter for a full activity feed, not for the narrower
    who-unlocked-this-lock use case this was first built for. Add them
    here if/when this expands into a general activity feed.
    """

    # description is inherited from AdcResourceAttributes and already
    # covers the human-readable summary (e.g. "Unlocked by Chris Pulliam").

    unit_id: int = field(metadata={"description": "The Alarm.com system/unit ID this event belongs to."}, default=0)
    event_date: str = field(
        metadata={"description": "ISO 8601 timestamp of when the event occurred."}, default=""
    )
    device_id: int = field(
        metadata={"description": "The numeric device ID this event is associated with (not the full resource ID)."},
        default=0,
    )
    device_description: str = field(
        metadata={"description": "Human-readable name of the device this event is associated with."}, default=""
    )
    event_type: int = field(metadata={"description": "Numeric Alarm.com event type code."}, default=-1)
    event_type_name: str = field(
        metadata={"description": "Human-readable event type name, e.g. 'DoorUnlocked', 'LightTurnedOn'."},
        default="Unknown",
    )
    global_device_id: str = field(
        metadata={
            "description": (
                "Combined unit-and-device resource ID (e.g. '110353471-1201') - "
                "matches this integration's own resource_id format for devices."
            )
        },
        default="",
    )
    secondary_description: str | None = field(
        metadata={"description": "Additional context, e.g. 'by Chris' or 'by Web'."}, default=None
    )
    contact_id: str = field(
        metadata={
            "description": (
                "Alarm.com contact/user ID directly attributed to this event, when Alarm.com's own "
                "system was able to determine one - empty string when it wasn't (e.g. actions "
                "performed over a shared web/app login rather than a per-user keypad code)."
            )
        },
        default="",
    )
    extra_data: str | None = field(
        metadata={
            "description": (
                "Raw URL-encoded query string carrying event-type-specific extra fields - e.g. "
                "'ew_contact_id=223551299&lockedByKeypad=true&ew=Chris+Pulliam&ew_group_id=0' for a "
                "keypad-code lock unlock. Use parsed_extra_data below rather than parsing this directly."
            )
        },
        default=None,
    )

    @property
    def parsed_extra_data(self) -> dict[str, str]:
        """
        Parse extra_data's URL-encoded query string into a plain dict.

        Confirmed real keys seen for a keypad-code lock unlock:
        `ew_contact_id` (matches contact_id above), `ew` (the user's
        display name, e.g. "Chris Pulliam"), `lockedByKeypad` ("true"),
        `ew_group_id`. Other event types carry entirely different keys in
        this same field (e.g. arm/disarm events carry `ew`/`ew_contact_user_type`
        without `lockedByKeypad`) - this only exposes the raw parsed dict,
        deliberately not a keypad-specific accessor, since extra_data's
        shape genuinely varies by event_type_name.
        """

        if not self.extra_data:
            return {}
        # parse_qs returns list values (a query string can repeat a key) -
        # every real key observed for this endpoint is single-valued, so
        # flatten defensively rather than exposing a components API a
        # caller would need to work around for the common case.
        return {key: values[0] for key, values in parse_qs(self.extra_data).items() if values}

    @property
    def unlocked_by_name(self) -> str | None:
        """
        Return the display name of who unlocked this device via keypad code, if known.

        Returns None both when this isn't a keypad-code unlock at all
        (extra_data lacks lockedByKeypad) and when Alarm.com's own system
        didn't attribute the unlock to a specific person (e.g. a shared
        web/app session) - both are genuinely "unknown", not modeled as
        two different states, since neither gives an automation anything
        actionable to use.
        """

        parsed = self.parsed_extra_data
        if parsed.get("lockedByKeypad") != "true":
            return None
        return parsed.get("ew") or None

    @property
    def unlock_method(self) -> str | None:
        """
        Return a normalized description of how this device was unlocked, if known.

        Added in response to real user feedback (GitHub issue #79): who
        unlocked a door doesn't get cleared/reset by every subsequent
        unlock, since not every unlock method generates a distinct,
        attributable event in the first place - a manual/inside turn may
        not even be logged as its own event by Alarm.com for some lock
        models. Method is a more reliable signal than name for gating an
        automation on "was this actually a keypad entry", independent of
        whether a name happens to be attached.

        Confirmed real values, from captured extra_data:
        - "keypad": lockedByKeypad=true (a code was entered at the panel/keypad)
        - "remote": unlock_method=ZwaveUnlock (Alarm.com's own UI describes
          this as "Unlocked remotely" - i.e. from the app or web portal)
        - "manual": unlock_method=ManualUnlock (the lock's own thumbturn/handle)

        Returns None when extra_data carries neither field - a genuinely
        unknown method, not a fourth category to model.
        """

        parsed = self.parsed_extra_data
        if parsed.get("lockedByKeypad") == "true":
            return "keypad"
        method = parsed.get("unlock_method")
        if method == "ManualUnlock":
            return "manual"
        if method == "ZwaveUnlock":
            return "remote"
        return None


@dataclass
class HistoryEvent(AdcResource[HistoryEventAttributes]):
    """
    A single activity history event resource.

    Uses AdcResource (not AdcDeviceResource) as its base, matching
    TroubleCondition rather than any of the device platforms - a history
    event has no persistent, ongoing state of its own to represent, it's
    a point-in-time record.
    """

    resource_type = ResourceType.HISTORY_EVENT
    attributes_type = HistoryEventAttributes
