"""
Tests for HistoryEvent/HistoryEventAttributes (models/history_event.py).

Uses the actual raw JSON:API attributes captured from a real Alarm.com
account's activity/history-event response (GitHub issue #79's
investigation) rather than invented fixture data - this is an entirely
undocumented endpoint, so testing against real captured shapes matters
more here than almost anywhere else in this codebase.
"""

from custom_components.alarmdotcom._pyalarmdotcomajax.models.history_event import (
    HistoryEvent,
)
from custom_components.alarmdotcom._pyalarmdotcomajax.models.jsonapi import Resource

# Real captured event: a keypad-code unlock with a specific person attributed.
KEYPAD_UNLOCK_ATTRIBUTES = {
    "description": "Unlocked by Chris Pulliam",
    "unitId": 110353471,
    "eventDate": "2026-07-14T02:22:56.307Z",
    "date": "2026-07-14T02:22:56.307Z",
    "deviceId": 1201,
    "deviceDescription": "Front Door",
    "eventType": 90,
    "eventTypeName": "DoorUnlocked",
    "globalDeviceId": "110353471-1201",
    "correlatedEventId": 0,
    "secondaryDescription": "by Chris",
    "contactId": "223551299",
    "extraData": "ew_contact_id=223551299&lockedByKeypad=true&ew=Chris+Pulliam&ew_group_id=0&has_sd_card=1&has_recording_rules=1",
}

# Real captured event: the same lock, unlocked over a shared web session -
# genuinely different in a way that matters: contactId is empty and
# extraData carries no lockedByKeypad flag at all.
WEB_UNLOCK_ATTRIBUTES = {
    "description": "Unlocked (Unlocked remotely)",
    "unitId": 110353471,
    "eventDate": "2026-07-13T23:34:32.063Z",
    "date": "2026-07-13T23:34:32.063Z",
    "deviceId": 1201,
    "deviceDescription": "Front Door",
    "eventType": 90,
    "eventTypeName": "DoorUnlocked",
    "globalDeviceId": "110353471-1201",
    "correlatedEventId": None,
    "secondaryDescription": None,
    "contactId": "",
    "extraData": "unlock_method=ZwaveUnlock&ew=&has_sd_card=1&has_recording_rules=1",
}

# Real captured event: a manual (non-remote, non-keypad) unlock, a
# different lock on the same account.
MANUAL_UNLOCK_ATTRIBUTES = {
    "description": "Unlocked (Manually unlocked)",
    "unitId": 110353471,
    "eventDate": "2026-07-13T23:35:28.823Z",
    "date": "2026-07-13T23:35:28.823Z",
    "deviceId": 1200,
    "deviceDescription": "Patio Door",
    "eventType": 90,
    "eventTypeName": "DoorUnlocked",
    "globalDeviceId": "110353471-1200",
    "correlatedEventId": None,
    "secondaryDescription": None,
    "contactId": "",
    "extraData": "unlock_method=ManualUnlock&ew=&has_sd_card=1&has_recording_rules=1",
}


def _make_event(event_id: str, attributes: dict) -> HistoryEvent:
    """Build a HistoryEvent from a raw attributes dict, matching a real JSON:API resource object."""
    resource = Resource(id=event_id, type="activity/history-event", attributes=attributes)
    return HistoryEvent(api_resource=resource)


def test_keypad_unlock_exposes_the_attributed_name() -> None:
    """The actual case issue #79 needs: a keypad unlock with a real name attached."""
    event = _make_event("M-1687518963333", KEYPAD_UNLOCK_ATTRIBUTES)

    assert event.attributes.unlocked_by_name == "Chris Pulliam"
    assert event.attributes.contact_id == "223551299"
    assert event.attributes.event_type_name == "DoorUnlocked"
    assert event.attributes.global_device_id == "110353471-1201"


def test_web_session_unlock_has_no_attributed_name() -> None:
    """
    A web/app-session unlock is genuinely un-attributed at the Alarm.com level, not a parsing gap.

    contactId is empty and extraData carries no lockedByKeypad flag at
    all - unlocked_by_name correctly returns None here, distinguishing
    "we don't know who" from "we do know, and it's nobody" (there's no
    such state - Alarm.com just doesn't attribute this event type).
    """
    event = _make_event("M-1687392287737", WEB_UNLOCK_ATTRIBUTES)

    assert event.attributes.unlocked_by_name is None
    assert event.attributes.contact_id == ""


def test_manual_unlock_has_no_attributed_name() -> None:
    """A manual (non-keypad, non-remote) unlock is also correctly un-attributed."""
    event = _make_event("M-1687393117140", MANUAL_UNLOCK_ATTRIBUTES)

    assert event.attributes.unlocked_by_name is None


def test_parsed_extra_data_flattens_the_query_string() -> None:
    """parsed_extra_data returns a plain dict, not parse_qs's list-valued default."""
    event = _make_event("M-1687518963333", KEYPAD_UNLOCK_ATTRIBUTES)

    parsed = event.attributes.parsed_extra_data

    assert parsed["ew_contact_id"] == "223551299"
    assert parsed["ew"] == "Chris Pulliam"
    assert parsed["lockedByKeypad"] == "true"


def test_parsed_extra_data_handles_none_gracefully() -> None:
    """A history event with no extraData at all (many event types have none) doesn't crash."""
    attributes = dict(KEYPAD_UNLOCK_ATTRIBUTES)
    attributes["extraData"] = None
    event = _make_event("test-id", attributes)

    assert event.attributes.parsed_extra_data == {}
    assert event.attributes.unlocked_by_name is None


def test_camelcase_keys_are_correctly_decamelized() -> None:
    """
    Confirms the inherited CamelizerMixin behavior actually applies to this model.

    Not a redundant check - this is the one thing that would silently
    break every other test in this file if HistoryEventAttributes didn't
    actually inherit the camelCase-handling behavior the rest of this
    library relies on, since every field access above would just return
    the dataclass's own defaults instead of the real captured values.
    """
    event = _make_event("M-1687518963333", KEYPAD_UNLOCK_ATTRIBUTES)

    assert event.attributes.device_description == "Front Door"
    assert event.attributes.event_type_name == "DoorUnlocked"
    assert event.attributes.unit_id == 110353471


# --- unlock_method (added in response to real user feedback, GitHub issue #79) ---


def test_keypad_unlock_method_is_keypad() -> None:
    """A keypad-code unlock reports unlock_method as 'keypad'."""
    event = _make_event("M-1687518963333", KEYPAD_UNLOCK_ATTRIBUTES)

    assert event.attributes.unlock_method == "keypad"


def test_web_session_unlock_method_is_remote() -> None:
    """
    A web/app-session unlock reports unlock_method as 'remote'.

    Real captured extraData for this event is 'unlock_method=ZwaveUnlock' -
    Alarm.com's own UI describes this same event as "Unlocked remotely",
    which is why "remote" (not the raw "ZwaveUnlock" value) is what gets
    exposed - a normalized, human-meaningful value rather than Alarm.com's
    own internal naming.
    """
    event = _make_event("M-1687392287737", WEB_UNLOCK_ATTRIBUTES)

    assert event.attributes.unlock_method == "remote"


def test_manual_unlock_method_is_manual() -> None:
    """A manual (thumbturn/handle) unlock reports unlock_method as 'manual'."""
    event = _make_event("M-1687393117140", MANUAL_UNLOCK_ATTRIBUTES)

    assert event.attributes.unlock_method == "manual"


def test_unlock_method_is_none_when_extra_data_has_neither_field() -> None:
    """An event with no extraData at all reports unlock_method as None, not an error."""
    attributes = dict(KEYPAD_UNLOCK_ATTRIBUTES)
    attributes["extraData"] = None
    event = _make_event("test-id", attributes)

    assert event.attributes.unlock_method is None


def test_unlock_method_is_independent_of_unlocked_by_name() -> None:
    """
    unlock_method and unlocked_by_name are derived independently - one being set doesn't require the other.

    This is the actual point of adding unlock_method separately: a manual
    or remote unlock always has unlocked_by_name as None (Alarm.com never
    attributes those to a person), but should still report a real,
    non-None unlock_method - the two attributes answer genuinely
    different questions ("who" vs "how"), not one derived from the other.
    """
    event = _make_event("M-1687393117140", MANUAL_UNLOCK_ATTRIBUTES)

    assert event.attributes.unlocked_by_name is None
    assert event.attributes.unlock_method == "manual"
