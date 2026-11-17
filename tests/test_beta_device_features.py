"""Regression coverage for the adapted fork features and their HA wiring."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from _pyalarmdotcomajax.controllers.lights import LightController
from _pyalarmdotcomajax.events import DeviceActivityMessage, EventBroker, EventBrokerTopic
from _pyalarmdotcomajax.exceptions import UnsupportedOperation
from _pyalarmdotcomajax.websocket.client import WebSocketClient
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_COLOR_TEMP_KELVIN, ATTR_RGB_COLOR, ColorMode
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.alarmdotcom  # noqa: F401
from custom_components.alarmdotcom import camera_detection
from custom_components.alarmdotcom import event as platform
from custom_components.alarmdotcom.camera_detection import CameraDetectionSensor, detected_objects
from custom_components.alarmdotcom.const import DOMAIN, EVENT_SCENE
from custom_components.alarmdotcom.event import decode_scene
from custom_components.alarmdotcom.light import control_fn, supported_color_modes_fn


@pytest.mark.parametrize(("packed", "expected"), [
    (1.0, (1, "KeyPressed")), (30002.0, (2, "KeyPressed2x")),
    (60001.0, (1, "KeyPressed5x")), (20002.0, (2, "KeyHeldDown")),
    (0.0, None), (10000.0, None), (30001.5, None), (float("nan"), None), (None, None),
])
def test_scene_actions(packed, expected):
    """Only valid paddle actions may trigger an automation."""
    assert decode_scene(packed) == expected


@pytest.mark.parametrize(("event", "extra", "expected"), [
    (71, "cnff=Human%2CAnimal%2CVehicle", {"person", "animal", "vehicle"}),
    (71, "cnff=Parcel", {"package"}), (210, "category=4", {"package"}),
    (210, "category=105", {"person"}), (210, "category=102", {"vehicle"}),
    (210, "category=101", {"animal"}), (210, "category=garbage", set()),
    (302, "category=0", set()), (71, "token=private", set()),
])
def test_camera_classification(event, extra, expected):
    """Rule changes and unknown classifications must not create detections."""
    assert detected_objects(event, extra) == expected


def test_camera_analytics_debug_excludes_private_event_fields(caplog):
    """Report allowlisted classifications without raw input or unrelated events."""
    with caplog.at_level("DEBUG", logger=camera_detection.__name__):
        camera_detection.log_camera_detection(DeviceActivityMessage(
            id="123-45", event_type=71,
            extra="cnff=Human%2CVehicle%2Cunknown-private-value&token=private-token",
        ))
        camera_detection.log_camera_detection(DeviceActivityMessage(
            id="123-45", event_type=210, extra="category=99999",
        ))
        camera_detection.log_camera_detection(DeviceActivityMessage(
            id="123-45", event_type=163, extra="token=scene-secret",
        ))
    assert caplog.messages == [
        "Camera analytics event type=71 classifications=person, vehicle",
        "Camera analytics event type=210 classifications=none",
    ]


def test_activity_parser_preserves_device_scope_without_raw_fields():
    """Monitoring frames can lack timestamps, correlation fields, and state-event metadata."""
    bridge = SimpleNamespace(events=EventBroker())
    client = WebSocketClient(bridge)
    received = []
    bridge.events.subscribe(EventBrokerTopic.DEVICE_ACTIVITY, received.append)
    assert client._emit_device_activity({
        "UnitId": 123, "DeviceId": 45, "EventType": 163, "EventValue": 30001,
        "privateToken": "never-publish-this",
    })
    assert received == [DeviceActivityMessage(id="123-45", event_type=163, value=30001)]
    assert "never-publish-this" not in repr(received)
    assert not client._emit_device_activity({"EventType": 163})
    assert not client._emit_device_activity({"EventType": 15, "UnitId": 123, "DeviceId": 45})


async def test_repeated_camera_detection_extends_pulse_and_unload_cancels(hass, monkeypatch):
    """A repeated detection replaces its old timer and eventually returns to idle."""

    scheduled = []
    def later(_hass, seconds, callback):
        cancel = MagicMock()
        scheduled.append((seconds, callback, cancel))
        return cancel
    monkeypatch.setattr(camera_detection, "async_call_later", later)
    sensor = CameraDetectionSensor(SimpleNamespace(available=True), "123-45", "person")
    sensor.hass = hass
    sensor.async_write_ha_state = MagicMock()
    event = DeviceActivityMessage(id="123-45", event_type=210, extra="category=0")
    sensor._handle_activity(event)
    assert sensor.is_on
    sensor._handle_activity(event)
    scheduled[0][2].assert_called_once()
    assert scheduled[1][0] == 10
    scheduled[1][1](None)
    assert not sensor.is_on
    sensor._handle_activity(event)
    sensor._stop_timer()
    scheduled[2][2].assert_called_once()


@pytest.mark.parametrize(("rgb", "white", "dimmer", "expected"), [
    (True, True, True, {ColorMode.RGB, ColorMode.COLOR_TEMP}),
    (False, False, True, {ColorMode.BRIGHTNESS}),
    (False, False, False, {ColorMode.ONOFF}),
])
def test_color_capabilities_do_not_mix_brightness_with_color(rgb, white, dimmer, expected):
    """HA requires BRIGHTNESS and ONOFF to be standalone supported modes."""
    attributes = SimpleNamespace(supports_rgb_color_control=rgb, supports_white_light_color_control=white, is_dimmer=dimmer)
    controller = MagicMock()
    controller.get.return_value = SimpleNamespace(attributes=attributes)
    assert supported_color_modes_fn(controller, "light") == expected


@pytest.mark.parametrize(("options", "color"), [
    ({ATTR_RGB_COLOR: (255, 0, 128)}, {"hex_color": "#FF0080"}),
    ({ATTR_COLOR_TEMP_KELVIN: 2700}, {"percent_warmth": 100}),
    ({ATTR_COLOR_TEMP_KELVIN: 6500}, {"percent_warmth": 0}),
])
async def test_light_commands_include_selected_color(options, color):
    """Power and color changes both reach the controller."""
    controller = SimpleNamespace(turn_on=AsyncMock(), set_color=AsyncMock())
    await control_fn(controller, "light", "turn_on", options)
    controller.turn_on.assert_awaited_once_with("light")
    controller.set_color.assert_awaited_once_with("light", **color)


async def test_zero_brightness_turns_off_without_sending_a_color():
    """A brightness-zero command should not momentarily turn the light on."""
    controller = SimpleNamespace(turn_off=AsyncMock(), set_color=AsyncMock())
    await control_fn(controller, "light", "turn_on", {ATTR_BRIGHTNESS: 0, ATTR_RGB_COLOR: (255, 0, 0)})
    controller.turn_off.assert_awaited_once_with("light")
    controller.set_color.assert_not_awaited()


async def test_color_put_preserves_required_device_metadata():
    """ADC requires the device name and icon even when only changing color."""
    bridge = SimpleNamespace(request=AsyncMock(), _generate_request_url=MagicMock(return_value="https://example.test/light"))
    controller = LightController(bridge)
    controller._resources["123-45"] = SimpleNamespace(
        id="123-45", name="Test light",
        attributes=SimpleNamespace(supports_rgb_color_control=True, supports_white_light_color_control=True),
        api_resource=SimpleNamespace(attributes={"deviceIcon": {"icon": 12}, "lightLevel": 42}),
    )
    controller._request_reconcile = MagicMock()
    await controller.set_color("123-45", hex_color="#FF0080")
    body = bridge.request.await_args.kwargs["json"]
    assert body["deviceIcon"] == {"icon": 12}
    assert body["lightLevel"] == 42
    assert body["description"] == "Test light"
    assert body["hexColor"] == "#FF0080"
    controller._request_reconcile.assert_called_once_with("Light color changed")
    controller._resources["123-45"].attributes.supports_rgb_color_control = False
    with pytest.raises(UnsupportedOperation):
        await controller.set_color("123-45", hex_color="#FF0080")


async def test_scene_platform_publishes_scoped_automation_events(hass, monkeypatch):
    """Real broker delivery reaches the HA bus with a registry device ID."""


    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, "123-45")})
    broker = EventBroker()
    lights = MagicMock()
    lights.__iter__.return_value = [SimpleNamespace(id="123-45")]
    lights.get.side_effect = lambda resource_id: object() if resource_id == "123-45" else None
    entry.runtime_data = SimpleNamespace(hub=SimpleNamespace(api=SimpleNamespace(lights=lights, events=broker)))
    monkeypatch.setattr(platform, "device_info_fn", lambda *_: DeviceInfo(identifiers={(DOMAIN, "123-45")}))
    entities = []
    received = []
    hass.bus.async_listen(EVENT_SCENE, lambda event: received.append(event.data))
    await platform.async_setup_entry(hass, entry, entities.extend)
    assert len(entities) == 2
    broker.publish(DeviceActivityMessage(id="123-45", event_type=163, value=30001.0))
    broker.publish(DeviceActivityMessage(id="another-device", event_type=163, value=30001.0))
    await hass.async_block_till_done()
    assert received == [{"device_id": device.id, "resource_id": "123-45", "scene": 1, "value": "KeyPressed2x"}]
