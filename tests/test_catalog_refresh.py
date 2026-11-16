"""
The periodic safety-net poll and the reconnect catch-up must re-fetch devices.

Regression cover for a sensor that stays wrong forever after one missed
websocket event: A contact sensor was opened while the websocket
was between connections, Alarm.com recorded it as open, and Home Assistant
kept showing it closed for hours. Both recovery paths call
DeviceCatalogController._refresh(), which used `.pop()` to read its only target
id. The first call emptied the set, so every later call returned at the
"requires target ids" guard without a request - and every device controller
(sensors, partitions, locks, ...) takes its data from the catalog.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from _pyalarmdotcomajax import AlarmBridge
from _pyalarmdotcomajax.controllers.device_catalogs import DeviceCatalogController
from _pyalarmdotcomajax.controllers.sensors import SensorController
from _pyalarmdotcomajax.events import EventBroker
from _pyalarmdotcomajax.models.jsonapi import Resource
from _pyalarmdotcomajax.models.sensor import SensorState
from _pyalarmdotcomajax.websocket import client as ws_client
from _pyalarmdotcomajax.websocket.client import RawResourceEventMessage, WebSocketClient
from _pyalarmdotcomajax.websocket.messages import EventWSMessage

import custom_components.alarmdotcom  # noqa: F401

# Importing the component runs its sys.path shim, which must happen before the
# bare `_pyalarmdotcomajax` imports below resolve; see test_sensor_websocket_state.
SYSTEM_ID = "22713253"
SENSOR_ID = "112674692-22"

# Attribute payload as Alarm.com returns it for a NetworX contact zone.
SENSOR_ATTRIBUTES: dict[str, Any] = {
    "deviceType": 1,
    "openClosedStatus": 2,
    "state": 1,
    "isFlexIo": False,
    "deviceRole": 0,
    "displayStateText": "Closed",
    "isMonitoringEnabled": True,
    "sensorNamingFormat": 4,
    "supportsBypass": False,
    "supportsImmediateBypass": False,
    "isBypassed": False,
    "managedDeviceType": 14,
    "hasState": True,
    "canBeRenamed": True,
    "canBeDeleted": False,
    "canAccessWebSettings": True,
    "canAccessAppSettings": False,
    "webSettings": 159,
    "canAccessTroubleshootingWizard": False,
    "troubleshootingWizard": None,
    "addDeviceResource": 0,
    "canBeAssociatedToVideoDevice": True,
    "associatedCameraDeviceIds": {},
    "macAddress": "",
    "manufacturer": None,
    "isAssignedToCareReceiver": False,
    "isOAuth": False,
    "isZWave": False,
    "supportsCommandClassBasic": False,
    "isMalfunctioning": False,
    "isZWaveWakeupNode": False,
    "unitSupportsRemovingWakeupNode": False,
    "primaryAssociatedDeviceIds": None,
    "showDeletionMessage": False,
    "isMatter": False,
    "matterAssociatedIdToNameMap": None,
    "matterParentNodeId": None,
    "canBeSaved": True,
    "canChangeDescription": True,
    "description": "A contact sensor",
    "deviceModelId": 110,
    "canConfirmStateChange": True,
    "canReceiveCommands": False,
    "remoteCommandsEnabled": True,
    "hasPermissionToChangeState": True,
    "deviceIcon": {"icon": 317},
    "batteryLevelNull": None,
    "batteryLevelClassification": None,
    "batteryLevelPct": None,
}


class FakeBridge:
    """Just enough of AlarmBridge for a catalog and its sensor sub-controller."""

    def __init__(self) -> None:
        self.events = EventBroker()
        self.omit_window = False
        self.window = {"state": SensorState.CLOSED.value, "openClosedStatus": 2, "displayStateText": "Closed"}
        self.get = AsyncMock(side_effect=self._get)

    async def _get(self, path: Any, ids: Any, **_: Any) -> SimpleNamespace:
        attributes = copy.deepcopy(SENSOR_ATTRIBUTES) | self.window
        return SimpleNamespace(
            data=Resource.from_dict(
                {"id": SYSTEM_ID, "type": "settings/manage-devices/device-catalog", "attributes": {}}
            ),
            included=[] if self.omit_window else [Resource.from_dict({"id": SENSOR_ID, "type": "devices/sensor", "attributes": attributes})],
        )


async def _settle() -> None:
    """Let the provider's fire-and-forget pushes to sub-controllers run."""
    for _ in range(5):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_every_refresh_refetches_the_catalog_and_updates_sensors() -> None:
    """A sensor changed while no event arrived is corrected by the next refresh, and every one after it."""
    bridge = FakeBridge()
    catalog = DeviceCatalogController(bridge)  # type: ignore[arg-type]
    sensors = SensorController(bridge, catalog)  # type: ignore[arg-type]

    await catalog.initialize([SYSTEM_ID])
    await sensors.initialize()
    await _settle()
    assert sensors[SENSOR_ID].attributes.state == SensorState.CLOSED

    # The window opens while the websocket is down: no event ever arrives.
    bridge.window = {"state": SensorState.OPEN.value, "openClosedStatus": 3, "displayStateText": "Open"}

    # What the hub's 5-minute poll and the RECONNECTED catch-up both call.
    for expected_calls in (2, 3):
        await catalog._refresh()
        await _settle()
        assert bridge.get.await_count == expected_calls
        assert bridge.get.await_args.args[1] == SYSTEM_ID

    assert sensors[SENSOR_ID].attributes.state == SensorState.OPEN


@pytest.mark.asyncio
async def test_refresh_keeps_its_single_target_id() -> None:
    """Reading the id must not consume it."""
    bridge = FakeBridge()
    catalog = DeviceCatalogController(bridge)  # type: ignore[arg-type]

    await catalog.initialize([SYSTEM_ID])

    assert catalog._target_device_ids == {SYSTEM_ID}


def _ws_event(event_type: int, word: str) -> RawResourceEventMessage:
    """Build a raw Alarm.com frame for zone 22, as the websocket delivers it."""
    frame = (
        '{"EventDateUtc":"2026-10-14T14:10:00.000Z","UnitId":112674692,"DeviceId":22,'
        f'"EventType":{event_type},"EventValue":0.0,"CorrelatedId":null,'
        f'"QstringForExtraData":"openClosedStatusWord={word}","DeviceType":1}}'
    )
    return RawResourceEventMessage(ws_message=EventWSMessage.from_json(frame))


@pytest.mark.asyncio
async def test_a_response_older_than_an_event_does_not_undo_it() -> None:
    """
    The window opens while a refresh is in flight: the refresh must not close it again.

    Turning the periodic poll back on makes this race reachable every few minutes.
    """
    bridge = FakeBridge()
    catalog = DeviceCatalogController(bridge)  # type: ignore[arg-type]
    sensors = SensorController(bridge, catalog)  # type: ignore[arg-type]
    await catalog.initialize([SYSTEM_ID])
    await sensors.initialize()
    await _settle()

    release = asyncio.Event()
    snapshot_before_the_event = bridge._get

    async def slow_get(path: Any, ids: Any, **kwargs: Any) -> SimpleNamespace:
        response = await snapshot_before_the_event(path, ids, **kwargs)  # still says closed
        await release.wait()
        return response

    bridge.get.side_effect = slow_get
    refresh = asyncio.create_task(catalog._refresh())
    await _settle()

    await sensors._base_handle_event(_ws_event(15, "open"))  # Opened, mid-request
    assert sensors[SENSOR_ID].attributes.state == SensorState.OPEN

    release.set()
    await refresh
    await _settle()
    assert sensors[SENSOR_ID].attributes.state == SensorState.OPEN

    # A refresh sent after the event is newer than it and does apply.
    bridge.get.side_effect = bridge._get
    await catalog._refresh()
    await _settle()
    assert sensors[SENSOR_ID].attributes.state == SensorState.CLOSED


def _bridge_with_fake_catalog() -> tuple[AlarmBridge, AsyncMock]:
    bridge = AlarmBridge()
    bridge._initialized = True
    catalog_refresh = AsyncMock()
    bridge._device_catalogs = SimpleNamespace(initialized=True, _refresh=catalog_refresh)  # type: ignore[assignment]
    return bridge, catalog_refresh


@pytest.mark.asyncio
async def test_reconcile_requests_are_coalesced() -> None:
    """A burst of requests costs one fetch."""
    bridge, catalog_refresh = _bridge_with_fake_catalog()

    for reason in ("websocket connected", "opened/closed event", "opened/closed event"):
        bridge.request_reconcile(reason, delay_s=0)
    await bridge._reconcile_task

    assert catalog_refresh.await_count == 1


@pytest.mark.asyncio
async def test_a_request_during_a_fetch_gets_a_fetch_of_its_own() -> None:
    """The in-flight fetch predates the request, so it cannot answer it."""
    bridge, catalog_refresh = _bridge_with_fake_catalog()
    in_fetch, release = asyncio.Event(), asyncio.Event()

    async def blocking_refresh() -> None:
        in_fetch.set()
        await release.wait()

    catalog_refresh.side_effect = blocking_refresh

    bridge.request_reconcile("websocket connected", delay_s=0)
    await in_fetch.wait()
    bridge.request_reconcile("opened/closed event", delay_s=0)
    release.set()
    await bridge._reconcile_task

    assert catalog_refresh.await_count == 2


@pytest.mark.asyncio
async def test_opened_closed_asks_for_a_reconcile() -> None:
    """The pulse settles to an assumed closed; Alarm.com gets the final word."""
    bridge = FakeBridge()
    bridge.request_reconcile = MagicMock()  # type: ignore[attr-defined]
    catalog = DeviceCatalogController(bridge)  # type: ignore[arg-type]
    sensors = SensorController(bridge, catalog)  # type: ignore[arg-type]
    await catalog.initialize([SYSTEM_ID])
    await sensors.initialize()
    await _settle()

    await sensors._base_handle_event(_ws_event(100, "open"))

    bridge.request_reconcile.assert_called_once()
    sensors._cancel_opened_closed_settle(SENSOR_ID)


@pytest.mark.asyncio
async def test_first_connection_and_planned_replacements_reconcile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neither emits RECONNECTED, so nothing else would catch up on events lost in the gap."""
    monkeypatch.setattr(ws_client, "WS_TOKEN_LIFETIME_S", 0.01)

    client = WebSocketClient(MagicMock())
    client._authenticate = AsyncMock(return_value=None)
    connects: list[str] = []

    @contextlib.asynccontextmanager
    async def fake_ws_connect(url: str, **_kwargs: object) -> Any:
        connects.append(url)
        if len(connects) > 3:
            raise asyncio.CancelledError
        socket = MagicMock()
        socket.close_code = None
        yield socket

    async def never_returns(_socket: object) -> None:
        await asyncio.sleep(3600)

    client._bridge.ws_connect = fake_ws_connect
    client._read_messages = never_returns  # type: ignore[method-assign]

    with pytest.raises(asyncio.CancelledError):
        await client._event_reader()

    # The first connection plus two planned replacements.
    assert client._bridge.request_reconcile.call_count == 3


async def test_missing_device_requires_three_consecutive_polls():
    """A temporary omission preserves entities, a persistent deletion removes them."""
    bridge = FakeBridge()
    catalog = DeviceCatalogController(bridge)
    sensors = SensorController(bridge, catalog)
    await catalog.initialize([SYSTEM_ID])
    await sensors.initialize()
    await _settle()
    bridge.omit_window = True
    for _ in range(2):
        await catalog._refresh()
        await _settle()
    assert SENSOR_ID in sensors
    bridge.omit_window = False
    await catalog._refresh()
    await _settle()
    bridge.omit_window = True
    for _ in range(2):
        await catalog._refresh()
        await _settle()
    assert SENSOR_ID in sensors
    await catalog._refresh()
    await _settle()
    assert SENSOR_ID not in sensors
