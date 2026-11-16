"""
Tests for AdcBatterySummarySensor in sensor.py.

Covers the account-wide low/critical battery count sensors - the one part
of this platform that isn't per-device, so it needs its own dedicated
coverage rather than being implicitly exercised by the per-device tests.
"""

from unittest.mock import MagicMock

from custom_components.alarmdotcom._pyalarmdotcomajax.models.base import BatteryLevel
from custom_components.alarmdotcom.const import DOMAIN
from custom_components.alarmdotcom.sensor import AdcBatterySummarySensor


def _make_device(name: str, battery_level: BatteryLevel | None) -> MagicMock:
    """Build a mock managed device with the given name and battery classification."""
    device = MagicMock()
    device.name = name
    device.attributes.battery_level_classification = battery_level
    return device


def _make_hub(devices: dict[str, MagicMock]) -> MagicMock:
    """Build a mock hub whose managed_devices dict-like object returns the given devices."""
    hub = MagicMock()
    hub.config_entry.entry_id = "test-entry-id"
    hub.api.active_system.id = "system-1"
    hub.api.managed_devices.values.return_value = list(devices.values())
    return hub


def test_counts_only_devices_matching_the_configured_level() -> None:
    """A LOW sensor counts only LOW devices, ignoring CRITICAL/HIGH/None ones."""
    hub = _make_hub(
        {
            "front_door": _make_device("Front Door", BatteryLevel.LOW),
            "back_door": _make_device("Back Door", BatteryLevel.LOW),
            "garage": _make_device("Garage", BatteryLevel.CRITICAL),
            "motion": _make_device("Motion", BatteryLevel.HIGH),
            "thermostat": _make_device("Thermostat", None),
        }
    )

    sensor = AdcBatterySummarySensor(hub=hub, level=BatteryLevel.LOW, name="Low Battery Count")

    assert sensor.native_value == 2
    assert sensor.extra_state_attributes == {"devices": ["Back Door", "Front Door"]}


def test_critical_sensor_counts_independently_from_low() -> None:
    """The CRITICAL sensor and the LOW sensor count independently, not overlapping."""
    hub = _make_hub(
        {
            "garage": _make_device("Garage", BatteryLevel.CRITICAL),
            "front_door": _make_device("Front Door", BatteryLevel.LOW),
        }
    )

    sensor = AdcBatterySummarySensor(hub=hub, level=BatteryLevel.CRITICAL, name="Critical Battery Count")

    assert sensor.native_value == 1
    assert sensor.extra_state_attributes == {"devices": ["Garage"]}


def test_zero_matching_devices_reports_zero_not_an_error() -> None:
    """No devices at a given battery level is a normal, valid state - zero, not a crash."""
    hub = _make_hub({"front_door": _make_device("Front Door", BatteryLevel.HIGH)})

    sensor = AdcBatterySummarySensor(hub=hub, level=BatteryLevel.CRITICAL, name="Critical Battery Count")

    assert sensor.native_value == 0
    assert sensor.extra_state_attributes == {"devices": []}


def test_recompute_updates_after_a_device_changes_level() -> None:
    """A subsequent recompute (as would happen on a real resource-update event) reflects new state."""
    devices = {"front_door": _make_device("Front Door", BatteryLevel.HIGH)}
    hub = _make_hub(devices)

    sensor = AdcBatterySummarySensor(hub=hub, level=BatteryLevel.LOW, name="Low Battery Count")
    assert sensor.native_value == 0

    devices["front_door"].attributes.battery_level_classification = BatteryLevel.LOW
    sensor._recompute()

    assert sensor.native_value == 1
    assert sensor.extra_state_attributes == {"devices": ["Front Door"]}


def test_attaches_to_the_system_device() -> None:
    """The summary sensor attaches to the account's System device, not a per-device one."""
    hub = _make_hub({})

    sensor = AdcBatterySummarySensor(hub=hub, level=BatteryLevel.LOW, name="Low Battery Count")

    assert sensor.device_info == {"identifiers": {(DOMAIN, "system-1")}}
