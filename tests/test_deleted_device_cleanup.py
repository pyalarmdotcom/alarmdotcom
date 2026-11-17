"""
A device Alarm.com drops goes away completely, and nothing left behind can break the connection.

Seen on 2026-10-14: a partition and two motion zones disappeared from the account. Only each device's main entity
removed itself. The partition's malfunction, battery and debug entities were still subscribed to the vanished
resource, and on the next connection event their handler raised KeyError. The exception escaped the event broker,
so every websocket reconnect failed, the hub gave up and scheduled a reload, and the reload failed to unload for the
same reason: the integration stayed dead until Home Assistant restarted.
"""

# Importing the component runs its sys.path shim, which must happen before the bare `_pyalarmdotcomajax`
# imports below resolve; see test_sensor_websocket_state.
import custom_components.alarmdotcom  # noqa: F401, I001

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from _pyalarmdotcomajax.events import EventBroker, EventBrokerTopic, ResourceEventMessage
from _pyalarmdotcomajax.websocket.client import ConnectionEvent, WebSocketState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alarmdotcom.const import DOMAIN
from custom_components.alarmdotcom.entity import AdcEntity, available_fn
from custom_components.alarmdotcom.hub import AlarmHub

GONE = "112674692-128"


def _connection_event() -> ConnectionEvent:
    return ConnectionEvent(current_state=WebSocketState.DEAD, next_attempt_s=None)


def test_a_failing_subscriber_does_not_stop_the_others() -> None:
    """The websocket client publishes through here; one bad entity must not abort its reconnect."""
    broker = EventBroker()
    received: list[str] = []

    def broken(_message: object) -> None:
        raise KeyError(GONE)

    broker.subscribe(EventBrokerTopic.CONNECTION_EVENT, lambda _m: received.append("before"))
    broker.subscribe(EventBrokerTopic.CONNECTION_EVENT, broken)
    broker.subscribe(EventBrokerTopic.CONNECTION_EVENT, lambda _m: received.append("after"))

    broker.publish(_connection_event())

    assert received == ["before", "after"]


def test_a_subscriber_may_unsubscribe_while_being_called() -> None:
    """Removing an entity unsubscribes it, sometimes from inside the callback being delivered."""
    broker = EventBroker()
    received: list[str] = []
    unsubscribe = None

    def leave(_message: object) -> None:
        received.append("leaving")
        unsubscribe()

    unsubscribe = broker.subscribe(EventBrokerTopic.CONNECTION_EVENT, leave)
    broker.subscribe(EventBrokerTopic.CONNECTION_EVENT, lambda _m: received.append("other"))

    broker.publish(_connection_event())
    broker.publish(_connection_event())

    assert received == ["leaving", "other", "other"]


def test_an_entity_whose_resource_is_gone_is_unavailable() -> None:
    """available_fn used to index managed_devices directly and raise for a removed device."""
    hub = SimpleNamespace(available=True, api=SimpleNamespace(managed_devices={}))

    assert available_fn(hub, GONE) is False  # type: ignore[arg-type]


def test_an_entity_whose_resource_is_gone_removes_itself_instead_of_raising() -> None:
    """A connection event reaches every entity, including ones whose device has just been deleted."""
    entity = SimpleNamespace(
        resource_id=GONE,
        hub=SimpleNamespace(api=SimpleNamespace(managed_devices={})),
        hass=MagicMock(),
        remove=MagicMock(return_value="remove-coroutine"),
    )

    AdcEntity.event_handler(entity, _connection_event())  # type: ignore[arg-type]

    entity.hass.async_create_task.assert_called_once_with("remove-coroutine")


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Provide a live config entry to own the devices."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="Alarm.com")
    entry.add_to_hass(hass)
    return entry


def _device_with_entities(
    hass: HomeAssistant, entry: MockConfigEntry, resource_id: str, suffixes: list[str]
) -> dr.DeviceEntry:
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, resource_id)}, name=resource_id
    )
    for suffix in suffixes:
        er.async_get(hass).async_get_or_create(
            "binary_sensor", DOMAIN, f"{resource_id}_{suffix}", config_entry=entry, device_id=device.id
        )
    return device


async def test_a_deleted_resource_takes_its_device_and_all_its_entities(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Trouble, malfunction, battery and debug entities go with the device, not just the main entity."""
    gone = _device_with_entities(hass, entry, GONE, ["main", "malfunction", "trouble", "battery"])
    kept = _device_with_entities(hass, entry, "112674692-6", ["main", "trouble"])
    hub = SimpleNamespace(hass=hass, config_entry=entry)

    AlarmHub._remove_deleted_device(hub, ResourceEventMessage(topic=EventBrokerTopic.RESOURCE_DELETED, id=GONE))  # type: ignore[arg-type]
    await hass.async_block_till_done()

    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    assert devices.async_get(gone.id) is None
    assert er.async_entries_for_device(entities, gone.id, include_disabled_entities=True) == []
    assert devices.async_get(kept.id) is not None
    assert len(er.async_entries_for_device(entities, kept.id)) == 2


async def test_the_system_device_is_never_removed(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """The account-level service device holds the system buttons and summary sensors."""
    system = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "112674692")},
        name="PERRY's system",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    hub = SimpleNamespace(hass=hass, config_entry=entry)

    AlarmHub._remove_deleted_device(  # type: ignore[arg-type]
        hub, ResourceEventMessage(topic=EventBrokerTopic.RESOURCE_DELETED, id="112674692")
    )
    AlarmHub._remove_deleted_device(hub, ResourceEventMessage(topic=EventBrokerTopic.RESOURCE_DELETED, id="never-seen"))  # type: ignore[arg-type]
    await hass.async_block_till_done()

    assert dr.async_get(hass).async_get(system.id) is not None


async def test_removing_an_entity_already_removed_with_its_device_is_harmless(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """The entity's own removal and the hub's device removal both answer the same delete."""
    registry = er.async_get(hass)
    entity_entry = registry.async_get_or_create("binary_sensor", DOMAIN, f"{GONE}_main", config_entry=entry)
    entity = SimpleNamespace(
        hass=hass, entity_id=entity_entry.entity_id, registry_entry=entity_entry, _removal_requested=False
    )

    registry.async_remove(entity_entry.entity_id)
    await AdcEntity.remove(entity)  # type: ignore[arg-type]
    await AdcEntity.remove(entity)  # type: ignore[arg-type]

    assert registry.async_get(entity_entry.entity_id) is None
