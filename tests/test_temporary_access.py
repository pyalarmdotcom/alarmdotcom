"""Exercise credential preservation, HTTP parsing, validation, and account routing."""

import json
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _pyalarmdotcomajax import AlarmBridge
from _pyalarmdotcomajax.access import (
    AccessDocument,
    AccessValidationError,
    access_dates_match,
    build_access_payload,
    validate_period,
)
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_USER
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alarmdotcom.access_service import async_register_access_service
from custom_components.alarmdotcom.const import DOMAIN

USER = "900001"
SYSTEM = "900002"
START = "2027-01-05T17:00:00.000Z"
END = "2027-01-10T17:00:00.000Z"


def resource():
    """All values are synthetic, including the nonnumeric credential sentinel."""
    return {"id": int(USER), "type": "users/access/device-access", "attributes": {
        "userCode": "private-pin-sentinel", "weeklySchedule": None, "temporarySchedule": None,
        "userType": 23, "isAccessPaused": False, "unknownFutureField": {"keepThisKey": True},
    }, "relationships": {
        "user": {"data": {"id": USER, "type": "users/user"}},
        "accessPointCollectionsSummary": {"data": {
            "id": USER, "type": "users/access/access-point-collections-summary",
        }},
        "systemsWithAccessPlanAccess": {"data": [], "meta": {"count": "0"}},
    }}


def test_preserves_pin_unknown_fields_and_original_document():
    """Match the portal's plural write types without a JSON:API envelope."""
    original = resource()
    snapshot = deepcopy(original)
    payload = build_access_payload(original, USER, START, END)
    assert original == snapshot
    assert payload["userCode"] == "private-pin-sentinel"
    assert payload["unknownFutureField"] == {"keepThisKey": True}
    assert payload["type"] == "users/access/device-accesses"
    assert payload["user"] == {"type": "users/users", "id": USER}
    assert payload["accessPointCollectionsSummary"]["type"].endswith("summaries")
    assert payload["temporarySchedule"] == {"beginDateTime": START, "endDateTime": END}
    assert "data" not in payload
    assert "private-pin-sentinel" not in repr(AccessDocument.from_dict({"data": original}))


@pytest.mark.parametrize("case", ["wrong_user", "wrong_relation", "weekly", "plan", "unknown_relation", "missing_pin"])
async def test_invalid_resources_never_send_put(case):
    """Refuse unsupported or mismatched access documents before any mutation."""
    body = resource()
    if case == "wrong_user":
        body["id"] = "900099"
    elif case == "wrong_relation":
        body["relationships"]["user"]["data"]["id"] = "900099"
    elif case == "weekly":
        body["attributes"]["weeklySchedule"] = {"days": [1]}
    elif case == "plan":
        body["relationships"]["systemsWithAccessPlanAccess"]["data"] = [{"id": "900099"}]
    elif case == "unknown_relation":
        body["relationships"]["newRelationship"] = {"data": None}
    else:
        del body["attributes"]["userCode"]
    bridge = AlarmBridge()
    bridge.request = AsyncMock(return_value=AccessDocument.from_dict({"data": body}))
    with pytest.raises(AccessValidationError):
        await bridge.device_access.set_temporary_access(USER, SYSTEM, datetime.fromisoformat(START), datetime.fromisoformat(END))
    assert bridge.request.await_count == 1


@pytest.mark.parametrize(("start", "end"), [
    ("2027-01-05T12:00:00", "2027-01-10T12:00:00Z"),
    (END, START), (START, START),
])
def test_invalid_dates_rejected(start, end):
    """Never silently interpret naive dates in the server's local time zone."""
    with pytest.raises(AccessValidationError):
        validate_period(datetime.fromisoformat(start), datetime.fromisoformat(end))


def test_dates_normalize_to_utc():
    """Explicit local offsets preserve the intended instant."""
    assert validate_period(datetime.fromisoformat("2027-01-05T12:00:00-05:00"), datetime.fromisoformat(END)) == (START, END)


async def test_real_request_parser_and_http_payload(caplog):
    """Use the real bridge request method and parser with a fake HTTP transport."""
    calls = []

    @asynccontextmanager
    async def transport(method, url, *args, **kwargs):
        calls.append((method, url, kwargs))
        body = resource()
        if method == "put":
            body["attributes"]["temporarySchedule"] = kwargs["json"]["temporarySchedule"]
        response = AsyncMock(status=200)
        response.text.return_value = json.dumps({"data": body})
        yield response

    bridge = AlarmBridge()
    with patch.object(bridge, "create_request", transport):
        await bridge.device_access.set_temporary_access(USER, SYSTEM, datetime.fromisoformat(START), datetime.fromisoformat(END))
    assert [call[0] for call in calls] == ["get", "put"]
    assert calls[1][1].endswith(f"/users/access/deviceAccesses/{USER}")
    assert calls[1][2]["headers"] == {"context-id": SYSTEM}
    assert calls[1][2]["json"]["userCode"] == "private-pin-sentinel"
    assert "private-pin-sentinel" not in caplog.text


async def test_unconfirmed_save_is_reported():
    """A nominally successful response with unchanged dates is not a confirmed update."""
    bridge = AlarmBridge()
    bridge.request = AsyncMock(return_value=AccessDocument.from_dict({"data": resource()}))
    with pytest.raises(ValueError, match="did not confirm"):
        await bridge.device_access.set_temporary_access(USER, SYSTEM, datetime.fromisoformat(START), datetime.fromisoformat(END))
    writes = [call for call in bridge.request.call_args_list if call.args[0] == "put"]
    assert len(writes) == 1
    assert writes[0].kwargs["allow_login_repair"] is False


def account(hass, title):
    """Give each loaded account a distinct API instance."""
    entry = MockConfigEntry(domain=DOMAIN, title=title, data={})
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    entry.runtime_data = MagicMock()
    entry.runtime_data.hub.api.systems = [MagicMock(id=SYSTEM)]
    entry.runtime_data.hub.api.device_access.set_temporary_access = AsyncMock()
    return entry


async def test_action_routes_to_selected_live_account(hass):
    """Registration order cannot accidentally target another account."""
    first, second = account(hass, "Account one"), account(hass, "Account two")
    async_register_access_service(hass)
    await hass.services.async_call(DOMAIN, "set_temporary_access", {
        "config_entry_id": second.entry_id, "system_id": SYSTEM, "user_id": USER, "begin": START, "end": END,
    }, blocking=True)
    first.runtime_data.hub.api.device_access.set_temporary_access.assert_not_awaited()
    second.runtime_data.hub.api.device_access.set_temporary_access.assert_awaited_once()


async def test_schedule_write_requires_an_admin_user(hass):
    """Reject non-admin calls before reaching the Alarm.com API."""
    entry = account(hass, "Account")
    admin = await hass.auth.async_create_user("Admin", group_ids=[GROUP_ID_ADMIN])
    user = await hass.auth.async_create_user("User", group_ids=[GROUP_ID_USER])
    async_register_access_service(hass)
    data = {"config_entry_id": entry.entry_id, "system_id": SYSTEM, "user_id": USER, "begin": START, "end": END}
    update = entry.runtime_data.hub.api.device_access.set_temporary_access

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN, "set_temporary_access", data, blocking=True, context=Context(user_id=user.id),
        )
    update.assert_not_awaited()

    await hass.services.async_call(
        DOMAIN, "set_temporary_access", data, blocking=True, context=Context(user_id=admin.id),
    )
    update.assert_awaited_once()


async def test_action_blocks_wrong_system_and_hides_private_errors(hass):
    """Only a selected account's own systems can be used and errors stay private."""
    entry = account(hass, "Account")
    async_register_access_service(hass)
    data = {"config_entry_id": entry.entry_id, "system_id": "900099", "user_id": USER, "begin": START, "end": END}
    with pytest.raises(ServiceValidationError, match="does not belong"):
        await hass.services.async_call(DOMAIN, "set_temporary_access", data, blocking=True)
    update = entry.runtime_data.hub.api.device_access.set_temporary_access
    update.assert_not_awaited()
    update.side_effect = RuntimeError("private-pin-sentinel")
    data["system_id"] = SYSTEM
    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(DOMAIN, "set_temporary_access", data, blocking=True)
    assert "private-pin-sentinel" not in str(error.value)


@pytest.mark.parametrize(("begin", "end", "matches"), [
    ("2027-01-05T17:00:00Z", "2027-01-10T17:00:00+00:00", True),
    ("2027-01-05T12:00:00-05:00", "2027-01-10T12:00:00-05:00", True),
    ("2027-01-05T17:00:00.001Z", END, False),
    ("2027-01-05T17:00:00", END, False),
    ("invalid", END, False),
    (START, "2027-01-10T18:00:00Z", False),
])
def test_confirmation_compares_instants_not_strings(begin, end, matches):
    """Formatting differences are allowed; changed instants are never accepted."""
    body = resource()
    body["attributes"]["temporarySchedule"] = {"beginDateTime": begin, "endDateTime": end}
    assert access_dates_match(body, USER, START, END) is matches
    assert not access_dates_match(body, "900099", START, END)


async def test_stale_put_response_is_confirmed_with_one_read_only_request():
    """Check persisted state without issuing a second credential write."""
    bridge = AlarmBridge()
    before = resource()
    after = resource()
    after["attributes"]["temporarySchedule"] = {
        "beginDateTime": "2027-01-05T17:00:00Z", "endDateTime": "2027-01-10T17:00:00Z",
    }
    bridge.request = AsyncMock(side_effect=[AccessDocument(data=body) for body in (before, before, after)])
    await bridge.device_access.set_temporary_access(USER, SYSTEM, datetime.fromisoformat(START), datetime.fromisoformat(END))
    assert [call.args[0] for call in bridge.request.call_args_list] == ["get", "put", "get"]


@pytest.mark.parametrize("scheduled", [False, True])
async def test_read_action_manager_only_gets_and_filters_credentials(scheduled):
    """Read-back exposes a small allowlist and never writes or returns a PIN."""
    bridge = AlarmBridge()
    body = resource()
    body["attributes"]["credentialStatus"] = 1
    body["attributes"]["credentialStatusDesc"] = "private-pin-sentinel"
    if scheduled:
        body["attributes"]["temporarySchedule"] = {
            "beginDateTime": START, "endDateTime": END,
            "unexpectedSecret": "private-pin-sentinel",
        }
    bridge.request = AsyncMock(return_value=AccessDocument(data=body))
    result = await bridge.device_access.get_temporary_user_schedule(USER, SYSTEM)
    assert result == {
        "temporary_schedule": {"begin": START, "end": END} if scheduled else None,
        "credential_status": 1,
    }
    assert "private-pin-sentinel" not in json.dumps(result)
    bridge.request.assert_awaited_once()
    assert bridge.request.call_args.args[0] == "get"
    assert bridge.request.call_args.kwargs["headers"] == {"context-id": SYSTEM}


@pytest.mark.parametrize("change", ["wrong_user", "missing_schedule", "naive_date", "invalid_date"])
async def test_read_rejects_mismatched_or_ambiguous_schedule(change):
    """A read must not silently confirm a different user or invent time zones."""
    body = resource()
    if change == "wrong_user":
        body["id"] = "900099"
    elif change == "missing_schedule":
        del body["attributes"]["temporarySchedule"]
    else:
        body["attributes"]["temporarySchedule"] = {
            "beginDateTime": "invalid" if change == "invalid_date" else "2027-01-05T17:00:00",
            "endDateTime": END,
        }
    bridge = AlarmBridge()
    bridge.request = AsyncMock(return_value=AccessDocument(data=body))
    with pytest.raises(AccessValidationError):
        await bridge.device_access.get_temporary_user_schedule(USER, SYSTEM)


async def test_read_service_returns_response_from_selected_account(hass):
    """Standard HA response data is available to scripts and existing MCP bridges."""
    first, second = account(hass, "First"), account(hass, "Second")
    expected = {"temporary_schedule": {"begin": START, "end": END}, "credential_status": 3}
    for entry in (first, second):
        entry.runtime_data.hub.api.device_access.get_temporary_user_schedule = AsyncMock(return_value=expected)
    async_register_access_service(hass)
    result = await hass.services.async_call(DOMAIN, "get_temporary_user_schedule", {
        "config_entry_id": second.entry_id, "system_id": SYSTEM, "user_id": USER,
    }, blocking=True, return_response=True)
    assert result == expected
    first.runtime_data.hub.api.device_access.get_temporary_user_schedule.assert_not_awaited()
    second.runtime_data.hub.api.device_access.get_temporary_user_schedule.assert_awaited_once_with(USER, SYSTEM)
    second.runtime_data.hub.api.device_access.set_temporary_access.assert_not_awaited()


async def test_read_service_blocks_wrong_account_and_redacts_failures(hass):
    """Account routing and error privacy apply equally to read-only actions."""
    entry = account(hass, "Account")
    reader = AsyncMock(side_effect=RuntimeError("private-pin-sentinel"))
    entry.runtime_data.hub.api.device_access.get_temporary_user_schedule = reader
    async_register_access_service(hass)
    data = {"config_entry_id": entry.entry_id, "system_id": "900099", "user_id": USER}
    with pytest.raises(ServiceValidationError, match="does not belong"):
        await hass.services.async_call(DOMAIN, "get_temporary_user_schedule", data, blocking=True, return_response=True)
    reader.assert_not_awaited()
    data["system_id"] = SYSTEM
    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(DOMAIN, "get_temporary_user_schedule", data, blocking=True, return_response=True)
    assert "private-pin-sentinel" not in str(error.value)
