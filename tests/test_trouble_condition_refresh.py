"""Trouble records expire with a successful response, rather than a device deletion delay."""

# The component must install its bundled-library import path first.
import custom_components.alarmdotcom  # noqa: F401, I001

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from _pyalarmdotcomajax.controllers.trouble_conditions import TroubleConditionController
from _pyalarmdotcomajax.events import EventBroker, EventBrokerTopic
from _pyalarmdotcomajax.exceptions import ServiceUnavailable
from _pyalarmdotcomajax.models.jsonapi import Resource


def condition(resource_id: str) -> Resource:
    """Represent a live low-battery condition with a replaceable record ID."""
    return Resource.from_dict({
        "id": resource_id,
        "type": "troubleConditions/trouble-condition",
        "attributes": {"troubleConditionType": 15, "emberDeviceId": "system-22"},
    })


def controller() -> TroubleConditionController:
    """Use the real controller and event broker without a live account."""
    bridge = MagicMock()
    bridge.events = EventBroker()
    bridge.get = AsyncMock(return_value=SimpleNamespace(data=[condition("old")], included=[]))
    return TroubleConditionController(bridge)


async def test_replaced_condition_does_not_accumulate_or_warn(caplog):
    """Changing IDs leave one condition, with deletion notifications for summary sensors."""
    trouble = controller()
    deleted = []
    trouble._bridge.events.subscribe(EventBrokerTopic.RESOURCE_DELETED, deleted.append)
    await trouble.initialize()
    trouble._bridge.get.return_value.data = [condition("replacement")]
    await trouble._refresh()
    assert [item.id for item in trouble] == ["replacement"]
    assert [message.id for message in deleted] == ["old"]
    assert "was missing from Alarm.com's response" not in caplog.text


async def test_clear_then_new_condition_is_discovered():
    """An empty successful response clears trouble without disabling future discovery."""
    trouble = controller()
    await trouble.initialize()
    trouble._bridge.get.return_value.data = []
    await trouble._refresh()
    assert list(trouble) == []
    trouble._bridge.get.return_value.data = [condition("new")]
    await trouble._refresh()
    assert [item.id for item in trouble] == ["new"]


async def test_failed_refresh_preserves_active_conditions():
    """A network or authentication failure must not be treated as a clear response."""
    trouble = controller()
    await trouble.initialize()
    trouble._bridge.get.side_effect = ServiceUnavailable("synthetic outage")
    with pytest.raises(ServiceUnavailable):
        await trouble._refresh()
    assert [item.id for item in trouble] == ["old"]


async def test_unchanged_active_condition_is_kept():
    """A record still returned by Alarm.com remains active across polls."""
    trouble = controller()
    await trouble.initialize()
    for _ in range(4):
        await trouble._refresh()
    assert [item.id for item in trouble] == ["old"]
