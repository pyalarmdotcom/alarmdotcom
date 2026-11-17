"""Regression tests for provider-specific Alarm.com light discovery URLs."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from custom_components.alarmdotcom._pyalarmdotcomajax import AlarmBridge
from custom_components.alarmdotcom._pyalarmdotcomajax.controllers import AdcSuccessDocumentSingle


def test_single_light_uses_scoped_query():
    """A single light must not be converted into a /lights/{id} request."""
    path = AlarmBridge._build_light_discovery_path({"123-456"})
    assert path == "devices/lights?ids%5B%5D=123-456"


def test_multiple_light_ids_are_sorted_and_encoded():
    """Multiple IDs must produce a stable, safely encoded query string."""
    path = AlarmBridge._build_light_discovery_path({"b/2", "a 1"})
    assert path == "devices/lights?ids%5B%5D=a+1&ids%5B%5D=b%2F2"


def test_empty_light_ids_are_rejected():
    """Do not accidentally issue an unscoped request."""
    with pytest.raises(ValueError, match="At least one light ID"):
        AlarmBridge._build_light_discovery_path(set())


@pytest.mark.parametrize("light_type", ["devices/light", "devices/switch", "provider/light"])
async def test_system_lights_relationship_drives_scoped_discovery(light_type):
    """Exercise parsed system detail through the actual scoped discovery path."""
    bridge = AlarmBridge()
    ids = [f"light-{number}" for number in range(4)]
    response = AdcSuccessDocumentSingle.from_dict({
        "data": {
            "id": "system-1", "type": "systems/system", "attributes": {},
            "relationships": {
                "lights": {"data": [{"id": item, "type": light_type} for item in ids], "meta": {"count": 4}},
                "locks": {"data": [{"id": "lock-1", "type": "devices/lock"}]},
            },
        },
    })
    bridge._available_device_catalogs = MagicMock(active_system_id="system-1", initialize=AsyncMock())
    bridge._systems = MagicMock(initialize=AsyncMock())
    bridge._device_catalogs = MagicMock(initialize=AsyncMock(), items=[], _included_resources=[])
    bridge._partitions = MagicMock(initialize=AsyncMock())
    bridge._auth_controller = MagicMock(has_trouble_conditions_service=False)
    bridge._lights = MagicMock(items=[], _target_device_ids=[], _refresh=AsyncMock())
    lights_response = MagicMock(data=[])
    bridge.get = AsyncMock(side_effect=[response, lights_response])
    with patch.object(AlarmBridge, "resource_controllers", new_callable=PropertyMock, return_value=[]):
        await bridge.fetch_full_state()
    assert bridge.get.await_args_list[0].args == ("systems/systems", "system-1")
    assert bridge.get.await_args_list[1].args == (AlarmBridge._build_light_discovery_path(set(ids)), None)
    bridge._lights._refresh.assert_awaited_once_with(pre_fetched=[])
