"""Update existing users' temporary access using the portal's captured format."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from _pyalarmdotcomajax.const import API_URL_BASE
from _pyalarmdotcomajax.models.jsonapi import JsonApiBaseElement

if TYPE_CHECKING:
    from _pyalarmdotcomajax import AlarmBridge


class AccessValidationError(ValueError):
    """An access validation failure containing only a fixed, public-safe message."""


@dataclass(repr=False)
class AccessDocument(JsonApiBaseElement):
    """Keep unknown access attributes in memory without exposing credentials in repr."""

    data: dict[str, Any] = field(repr=False)

    @classmethod
    def __pre_deserialize__(cls, d: dict[Any, Any]) -> dict[Any, Any]:
        """Preserve portal key spelling, including unknown nested attributes."""
        if "errors" in d or not isinstance(d.get("data"), dict):
            raise AccessValidationError("Expected a single access resource.")
        return d


def validate_period(begin: datetime, end: datetime) -> tuple[str, str]:
    """Require explicit time zones and an increasing interval, then serialize UTC."""
    if begin.utcoffset() is None or end.utcoffset() is None:
        raise AccessValidationError("Access dates must include a time zone or UTC offset.")
    if end <= begin:
        raise AccessValidationError("Access end must be after access start.")

    def utc_text(value: datetime) -> str:
        """Serialize one endpoint without relying on the machine time zone."""
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    return utc_text(begin), utc_text(end)


def build_access_payload(resource: dict[str, Any], user_id: str, begin: str, end: str) -> dict[str, Any]:
    """Flatten a fresh GET resource into the observed PUT shape, preserving fields."""
    if str(resource.get("id")) != user_id or resource.get("type") != "users/access/device-access":
        raise AccessValidationError("Access response does not match the requested user.")
    attributes = resource.get("attributes")
    relationships = resource.get("relationships")
    if not isinstance(attributes, dict) or not isinstance(relationships, dict):
        raise AccessValidationError("Access response is missing attributes or relationships.")
    if not {"temporarySchedule", "weeklySchedule", "userCode"} <= attributes.keys():
        raise AccessValidationError("Access response is missing required access fields.")
    if attributes.get("weeklySchedule") is not None:
        # Replacing a restricted weekly plan has not been captured or tested.
        raise AccessValidationError("Weekly access schedules cannot be replaced by this action.")
    if {"id", "type"} & attributes.keys() or attributes.keys() & relationships.keys():
        raise AccessValidationError("Access response contains conflicting fields.")
    payload = deepcopy(attributes)
    payload.update(id=user_id, type="users/access/device-accesses")
    relationship_types = {
        "user": ("users/user", "users/users"),
        "accessPointCollectionsSummary": (
            "users/access/access-point-collections-summary",
            "users/access/access-point-collections-summaries",
        ),
    }
    if relationships.keys() != {*relationship_types, "systemsWithAccessPlanAccess"}:
        raise AccessValidationError("Access response contains unsupported relationships.")
    for name, (read_type, write_type) in relationship_types.items():
        relation = relationships[name]
        data = relation.get("data") if isinstance(relation, dict) else None
        if not isinstance(data, dict) or str(data.get("id")) != user_id or data.get("type") != read_type:
            raise AccessValidationError("Access relationship does not match the requested user.")
        payload[name] = {"type": write_type, "id": user_id}
    plan = relationships["systemsWithAccessPlanAccess"]
    if not isinstance(plan, dict) or plan.get("data") != []:
        raise AccessValidationError("Access plans are not supported by this action.")
    payload["systemsWithAccessPlanAccess"] = []
    payload["temporarySchedule"] = {"beginDateTime": begin, "endDateTime": end}
    return payload


def access_dates_match(resource: dict[str, Any], user_id: str, begin: str, end: str) -> bool:
    """Compare timezone-aware instants, accepting equivalent server formatting."""
    if str(resource.get("id")) != user_id or resource.get("type") != "users/access/device-access":
        return False
    attributes = resource.get("attributes")
    schedule = attributes.get("temporarySchedule") if isinstance(attributes, dict) else None
    if not isinstance(schedule, dict):
        return False
    for key, expected in (("beginDateTime", begin), ("endDateTime", end)):
        actual = schedule.get(key)
        if not isinstance(actual, str):
            return False
        try:
            parsed = datetime.fromisoformat(actual)
            requested = datetime.fromisoformat(expected)
        except ValueError:
            return False
        # Never assign a machine-local zone to an ambiguous server timestamp.
        if parsed.utcoffset() is None or parsed.astimezone(UTC) != requested.astimezone(UTC):
            return False
    return True


def public_access_schedule(resource: dict[str, Any], user_id: str) -> dict[str, Any]:
    """Project an access document onto a strict credential-free response."""
    if str(resource.get("id")) != user_id or resource.get("type") != "users/access/device-access":
        raise AccessValidationError("Access response does not match the requested user.")
    attributes = resource.get("attributes")
    if not isinstance(attributes, dict) or "temporarySchedule" not in attributes:
        raise AccessValidationError("Access response is missing schedule information.")
    schedule = attributes["temporarySchedule"]
    public_schedule = None
    if schedule is not None:
        if not isinstance(schedule, dict):
            raise AccessValidationError("Access response contains an invalid temporary schedule.")
        try:
            begin = datetime.fromisoformat(schedule["beginDateTime"])
            end = datetime.fromisoformat(schedule["endDateTime"])
            start, finish = validate_period(begin, end)
        except (KeyError, TypeError, ValueError):
            raise AccessValidationError("Access response contains an invalid temporary schedule.") from None
        public_schedule = {"begin": start, "end": finish}
    # Preserve the server's numeric status without guessing at undocumented enum
    # meanings. Never return arbitrary attributes, descriptions, or PIN values.
    status = attributes.get("credentialStatus")
    return {
        "temporary_schedule": public_schedule,
        "credential_status": status if type(status) is int else None,
    }


class DeviceAccessManager:
    """Perform serialized read-modify-write operations without retaining access data."""

    def __init__(self, bridge: AlarmBridge) -> None:
        """Keep only the bridge and lock, never a cached PIN or access document."""
        self._bridge = bridge
        self._lock = asyncio.Lock()

    async def get_temporary_user_schedule(self, user_id: str, system_id: str) -> dict[str, Any]:
        """Read the current schedule without writing or retaining credential data."""
        if not all(value and value.isascii() and value.isdecimal() for value in (user_id, system_id)):
            raise AccessValidationError("User and system IDs must contain decimal digits only.")
        async with self._lock:
            current = await self._bridge.request(
                "get", f"{API_URL_BASE}users/access/deviceAccesses/{user_id}",
                success_response_class=AccessDocument, headers={"context-id": system_id},
            )
            return public_access_schedule(current.data, user_id)

    async def set_temporary_access(self, user_id: str, system_id: str, begin: datetime, end: datetime) -> None:
        """Update dates for one existing user and require a matching response."""
        if not all(value and value.isascii() and value.isdecimal() for value in (user_id, system_id)):
            raise AccessValidationError("User and system IDs must contain decimal digits only.")
        start, finish = validate_period(begin, end)
        url = f"{API_URL_BASE}users/access/deviceAccesses/{user_id}"
        async with self._lock:
            # Fetch immediately before writing so PINs and other fields are not
            # sourced from stale cached entity data or supplied by an automation.
            current = await self._bridge.request(
                "get", url, success_response_class=AccessDocument,
                headers={"context-id": system_id},
            )
            payload = build_access_payload(current.data, user_id, start, finish)
            updated = await self._bridge.request(
                "put", url, success_response_class=AccessDocument,
                headers={"context-id": system_id}, json=payload,
                # An expired login must not automatically replay a credential write.
                allow_login_repair=False,
            )
            # A 200 response confirms the server saved dates, not that every
            # panel/lock has finished synchronizing the credential.
            if access_dates_match(updated.data, user_id, start, finish):
                return
            # Some writes return a stale representation. Read the requested user
            # once to verify persisted dates, without replaying the credential PUT.
            confirmed = await self._bridge.request(
                "get", url, success_response_class=AccessDocument,
                headers={"context-id": system_id},
            )
            if not access_dates_match(confirmed.data, user_id, start, finish):
                raise AccessValidationError("Alarm.com did not confirm the requested access dates. Check the portal before retrying.")
