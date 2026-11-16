"""Advertised valves are fetched directly even when the device catalog omits them."""

import custom_components.alarmdotcom  # noqa: F401, I001

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from _pyalarmdotcomajax import AlarmBridge
from _pyalarmdotcomajax.models.base import ResourceType
from _pyalarmdotcomajax.models.jsonapi import Resource
from _pyalarmdotcomajax.models.water_valve import WaterValveState
from _pyalarmdotcomajax.websocket.client import ConnectionEvent, WebSocketState

from custom_components.alarmdotcom.valve import is_closed_fn

VALVE_ID = "system-1201"


def bridge_with_advertised_valves(ids: list[str]) -> AlarmBridge:
    """Keep the real valve controller while isolating unrelated account discovery."""
    bridge = AlarmBridge()
    system = Resource.from_dict({
        "id": "system", "type": "systems/system", "attributes": {},
        "relationships": {"waterValves": {"data": [
            {"id": device_id, "type": "devices/water-valve"} for device_id in ids
        ]}},
    })
    bridge._available_device_catalogs = MagicMock(active_system_id="system", initialize=AsyncMock())
    bridge._systems = MagicMock(initialize=AsyncMock(), items=[SimpleNamespace(api_resource=system)])
    bridge._device_catalogs.initialize = AsyncMock()
    bridge._partitions = MagicMock(initialize=AsyncMock())
    bridge._auth_controller = MagicMock(has_trouble_conditions_service=False)
    bridge._lights = MagicMock(items=[object()])
    bridge.get = AsyncMock(return_value=SimpleNamespace(
        data=Resource.from_dict({
            "id": VALVE_ID, "type": "devices/water-valve",
            "attributes": {"state": 2, "desiredState": 2, "hasState": False,
                           "hasPermissionToChangeState": True, "remoteCommandsEnabled": True,
                           "batteryLevelNull": None, "batteryLevelClassification": 0,
                           "canBeSaved": True, "canConfirmStateChange": True,
                           "canReceiveCommands": True},
        }), included=[],
    ))
    return bridge


async def test_advertised_valve_loads_without_catalog_included_data():
    """The reporter's locally verified direct-fetch fix reaches actual valve parsing."""
    bridge = bridge_with_advertised_valves([VALVE_ID])
    with patch.object(AlarmBridge, "resource_controllers", new_callable=PropertyMock,
                      return_value=[bridge.water_valves]):
        await bridge.fetch_full_state()
        bridge.get.assert_awaited_once_with(ResourceType.WATER_VALVE, VALVE_ID)
        assert bridge.water_valves[VALVE_ID].attributes.state == WaterValveState.CLOSED
        assert is_closed_fn(bridge.water_valves, VALVE_ID) is True
        # The periodic safety-net also fetches the direct endpoint after setup.
        await bridge.refresh_all_resources()
        assert bridge.get.await_count == 2


async def test_first_websocket_connection_rechecks_stale_valve_state():
    """The direct endpoint can correct the startup reading without a valve event."""
    bridge = bridge_with_advertised_valves([VALVE_ID])
    valve = bridge.water_valves
    await valve.initialize(target_device_ids=[VALVE_ID])
    assert is_closed_fn(valve, VALVE_ID) is True

    fresh_resource = Resource.from_dict({
        "id": VALVE_ID,
        "type": "devices/water-valve",
        "attributes": {
            **bridge.get.return_value.data.attributes,
            "state": 1,
            "desiredState": 1,
            "deviceModelId": 10541,
        },
    })
    bridge.get.return_value = SimpleNamespace(data=fresh_resource, included=[])
    await valve._base_handle_event(ConnectionEvent(current_state=WebSocketState.CONNECTED))

    assert bridge.get.await_count == 2
    bridge.get.assert_awaited_with(ResourceType.WATER_VALVE, VALVE_ID)
    assert is_closed_fn(valve, VALVE_ID) is False


async def test_account_without_valves_never_requests_valve_endpoint():
    """Preserve the no-device guard for accounts that do not offer this feature."""
    bridge = bridge_with_advertised_valves([])
    with patch.object(AlarmBridge, "resource_controllers", new_callable=PropertyMock,
                      return_value=[bridge.water_valves]):
        await bridge.fetch_full_state()
        await bridge.water_valves._base_handle_event(ConnectionEvent(current_state=WebSocketState.CONNECTED))
        await bridge.refresh_all_resources()
    bridge.get.assert_not_awaited()
    assert bridge.water_valves.items == []


@pytest.mark.parametrize(("state", "expected"), [(0, None), (1, False), (2, True)])
def test_valve_state_respects_known_and_unknown_values(state, expected):
    """Unknown must not be displayed as open; explicit reported states remain usable."""
    controller = MagicMock()
    controller.get.return_value = SimpleNamespace(attributes=SimpleNamespace(state=WaterValveState(state)))
    assert is_closed_fn(controller, VALVE_ID) is expected
