"""Keep portal-effective temperatures and live thermostat property updates working."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from _pyalarmdotcomajax.controllers.thermostats import ThermostatController
from _pyalarmdotcomajax.websocket.messages import PropertyChangeWSMessage

from custom_components.alarmdotcom.climate import current_temperature_fn


@pytest.mark.parametrize(("ambient", "forwarded", "expected"), [
    (73.0, 78.0, 78.0), (73.0, None, 73.0),
    (12.0, 0.0, 0.0), (None, None, None), (None, 21.0, 21.0),
])
def test_effective_temperature_matches_portal(ambient, forwarded, expected):
    """Prefer the effective reading without treating zero as missing."""
    resource = SimpleNamespace(attributes=SimpleNamespace(
        ambient_temp=ambient, forwarding_ambient_temp=forwarded,
    ))
    controller = SimpleNamespace(get=lambda _: resource)
    assert current_temperature_fn(controller, "synthetic-thermostat") == expected
    assert current_temperature_fn(SimpleNamespace(get=lambda _: None), "missing") is None


@pytest.mark.parametrize(("celsius", "value", "expected"), [
    (False, 7410, 74.1), (True, 7410, 23.4), (False, 0, 0.0), (True, 3200, 0.0),
])
async def test_live_temperature_property_updates_readings_and_requests_refresh(celsius, value, expected):
    """Parse real websocket-shaped input and run the actual controller handler."""
    bridge = SimpleNamespace(
        auth_controller=SimpleNamespace(use_celsius=celsius), request_reconcile=MagicMock(),
    )
    controller = ThermostatController(bridge)
    resource = SimpleNamespace(
        attributes=SimpleNamespace(ambient_temp=70.0, forwarding_ambient_temp=70.0, is_paired=False),
        api_resource=SimpleNamespace(attributes={"ambientTemp": 70.0, "forwardingAmbientTemp": 70.0}),
    )
    message = PropertyChangeWSMessage.from_dict({
        "UnitId": 900001, "DeviceId": 1200, "Property": 1, "PropertyValue": value,
        "ReportedDateUtc": "2026-10-30T12:00:00Z",
    })
    await controller._handle_event(resource, message)
    assert resource.api_resource.attributes == {"ambientTemp": expected, "forwardingAmbientTemp": expected}
    bridge.request_reconcile.assert_called_once_with("thermostat temperature changed")


@pytest.mark.parametrize(("paired", "forwarded"), [(True, 78.0), (False, 78.0), (True, 70.0)])
async def test_body_probe_event_preserves_remote_average_until_refresh(paired, forwarded):
    """Never overwrite a remote average with a single probe's websocket value."""
    bridge = SimpleNamespace(auth_controller=SimpleNamespace(use_celsius=False), request_reconcile=MagicMock())
    controller = ThermostatController(bridge)
    resource = SimpleNamespace(
        attributes=SimpleNamespace(ambient_temp=70.0, forwarding_ambient_temp=forwarded, is_paired=paired),
        api_resource=SimpleNamespace(attributes={"ambientTemp": 70.0, "forwardingAmbientTemp": forwarded}),
    )
    message = PropertyChangeWSMessage.from_dict({
        "UnitId": 900001, "DeviceId": 1200, "Property": 1, "PropertyValue": 7410,
        "ReportedDateUtc": "2026-10-30T12:00:00Z",
    })
    await controller._handle_event(resource, message)
    assert resource.api_resource.attributes["ambientTemp"] == 74.1
    assert resource.api_resource.attributes["forwardingAmbientTemp"] == forwarded
    bridge.request_reconcile.assert_called_once()
