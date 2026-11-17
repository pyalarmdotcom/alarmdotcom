"""Core API checks that also run without the release-specific HA test helper."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.climate import ClimateEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.alarmdotcom import _pyalarmdotcomajax as pyadc
from custom_components.alarmdotcom.camera import AlarmDotComCamera
from custom_components.alarmdotcom.climate import AdcClimateEntity
from custom_components.alarmdotcom.config_flow import ADCFlowHandler
from custom_components.alarmdotcom.device_trigger import TRIGGER_SCHEMA
from custom_components.alarmdotcom.entity import device_info_fn
from custom_components.alarmdotcom.hub import AlarmHub
from custom_components.alarmdotcom.schema import vol
from custom_components.alarmdotcom.webrtc_ws import async_get_webrtc_config


@pytest.mark.parametrize("celsius", [True, False])
def test_climate_temperatures_on_initialization_and_push(celsius):
    """Both core APIs expose units and all setpoints after live updates."""
    entity = AdcClimateEntity.__new__(AdcClimateEntity)
    entity.hub = MagicMock()
    entity.controller = MagicMock()
    entity.resource_id = "thermostat-1"
    description = entity.entity_description = MagicMock()
    description.temperature_fn.return_value = 21.5
    description.target_temperature_fn.return_value = None
    description.target_temperature_low_fn.return_value = 19.0
    description.target_temperature_high_fn.return_value = 24.0
    description.uses_celsius_fn.return_value = celsius
    entity.initiate_state()
    native = hasattr(ClimateEntity, "native_current_temperature")
    prefix = "native_" if native else ""
    assert getattr(entity, prefix + "current_temperature") == 21.5
    assert getattr(entity, prefix + "target_temperature") is None
    assert getattr(entity, prefix + "target_temperature_low") == 19.0
    assert getattr(entity, prefix + "target_temperature_high") == 24.0
    expected = UnitOfTemperature.CELSIUS if celsius else UnitOfTemperature.FAHRENHEIT
    assert getattr(entity, prefix + "temperature_unit") == expected
    description.temperature_fn.return_value = 22.0
    description.target_temperature_fn.return_value = 23.0
    entity.update_state(pyadc.ResourceEventMessage(topic=pyadc.EventBrokerTopic.RESOURCE_UPDATED, id=entity.resource_id))
    assert getattr(entity, prefix + "current_temperature") == 22.0
    assert getattr(entity, prefix + "target_temperature") == 23.0
    if native:
        assert "_attr_current_temperature" not in entity.__dict__
        assert "_attr_temperature_unit" not in entity.__dict__


@pytest.mark.parametrize("registered", [False, True])
def test_device_info_constructor_and_parent(registered):
    """Construction works for TypedDict and dataclass implementations."""
    hub = MagicMock()
    resource = MagicMock(id="sensor-1", system_id="system-1")
    resource.name = "Sensor"
    resource.attributes.mac_address = None
    resource.attributes.manufacturer = "Alarm.com"
    resource.attributes.device_model = "Sensor"
    hub.api.managed_devices = {"sensor-1": resource}
    hub.api.active_system.id = "system-1"
    hub.api.partitions.get_device_partition.return_value = None
    parent = MagicMock(id="parent-registry-id", identifiers={("alarmdotcom", "system-1")})
    with patch("custom_components.alarmdotcom.entity.dr.async_entries_for_config_entry", return_value=[parent] if registered else []):
        info = device_info_fn(hub, "sensor-1", None)
    values = info.as_dict() if hasattr(info, "as_dict") else info
    assert values["identifiers"] == {("alarmdotcom", "sensor-1")}
    assert values["manufacturer"] == "Alarm.com"
    assert values.get("via_device_id") == ("parent-registry-id" if registered else None)
    if not registered:
        assert "via_device_id" not in values
    assert isinstance(info, DeviceInfo) if hasattr(info, "as_dict") else isinstance(info, dict)


def test_schema_engine_matches_core():
    """Service and websocket schemas must accept core validators and markers."""
    schema = vol.Schema({vol.Required("entity_id"): cv.entity_id})
    assert schema({"entity_id": "camera.porch"}) == {"entity_id": "camera.porch"}
    with pytest.raises(vol.Invalid):
        schema({"entity_id": "invalid"})
    command_schema = async_get_webrtc_config._ws_schema
    assert command_schema({"id": 1, "type": "alarmdotcom/webrtc_config", "entity_id": "camera.porch"})["entity_id"] == "camera.porch"


def test_initial_config_form_uses_core_schema():
    """The initial form exposes a valid schema using the running core's engine."""
    result = asyncio.run(ADCFlowHandler().async_step_user())
    schema = result["data_schema"]
    assert schema({"username": "test", "password": "fake-password"})["username"] == "test"


def test_camera_state_never_exposes_credentials():
    """The actual camera class keeps stream credentials out of recorded state."""
    camera = AlarmDotComCamera.__new__(AlarmDotComCamera)
    camera._webrtc_config = {"janusToken": "fake-token", "proxyUrl": "fake-url"}
    assert camera.extra_state_attributes == {}


def test_hub_unloads_platforms_once():
    """The real hub closes its API and unloads platforms exactly once."""
    hub = AlarmHub.__new__(AlarmHub)
    hub._reconnect_task = None
    hub.close_jobs = []
    hub.api = MagicMock(close=AsyncMock())
    hub.hass = MagicMock()
    hub.hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hub.config_entry = MagicMock()
    assert asyncio.run(hub.close()) is True
    hub.api.close.assert_awaited_once()
    hub.hass.config_entries.async_unload_platforms.assert_awaited_once()


def test_scene_device_trigger_schema_uses_core_schema_library():
    """The new device-trigger schema must compose with the running core APIs."""

    config = TRIGGER_SCHEMA({
        "platform": "device", "domain": "alarmdotcom", "device_id": "device-1",
        "type": "scene_action", "subtype": "scene_001", "value": "KeyPressed2x",
    })
    assert config["value"] == "KeyPressed2x"
