"""
Tests for the bypass_sensor/unbypass_sensor services (_async_register_services in __init__.py).

GitHub issue #80: calling bypass_sensor without an explicit partition_id
crashed with `'PartitionController' object has no attribute 'values'` -
hub.api.partitions is iterable directly (via BaseController.__iter__),
it is not dict-like. There was previously zero test coverage for these
services at all, which is exactly how this shipped: a mock shaped like a
dict rather than the real iterable controller would have silently
"passed" this exact bug. FakePartitionController below is deliberately a
real list subclass, not a dict or a MagicMock with .values() available,
so this class of bug can't slip through unnoticed again.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.alarmdotcom import _async_register_services
from custom_components.alarmdotcom.auto_off import AutoOffManager
from custom_components.alarmdotcom.const import (
    ATTR_PARTITION_ID,
    ATTR_RESOURCE_ID,
    DOMAIN,
    SERVICE_BYPASS_SENSOR,
    SERVICE_UNBYPASS_SENSOR,
)

RESOURCE_ID = "109046804-1"
PARTITION_ID = "20392030"
SYSTEM_ID = "110353471"


class FakePartitionController(list):
    """
    A real list subclass standing in for PartitionController.

    Deliberately not a dict, and deliberately not a bare MagicMock -
    BaseController is iterable directly (yields resources via __iter__),
    it has no .values()/.keys()/.items(). A mock that happened to support
    .values() would defeat the entire point of this regression test.
    """

    def __init__(self, partitions: list) -> None:
        super().__init__(partitions)
        self.change_sensor_bypass = AsyncMock()


def _make_partition(partition_id: str, system_id: str) -> MagicMock:
    partition = MagicMock()
    partition.id = partition_id
    partition.system_id = system_id
    return partition


def _make_sensor(system_id: str, *, supports_bypass: bool = True) -> MagicMock:
    sensor = MagicMock()
    sensor.system_id = system_id
    sensor.attributes.supports_bypass = supports_bypass
    sensor.attributes.supports_immediate_bypass = False
    return sensor


def _make_hub(sensors: dict, partitions: list) -> MagicMock:
    hub = MagicMock()
    hub.api.sensors = sensors
    hub.api.partitions = FakePartitionController(partitions)
    return hub


@pytest.fixture
def config_entry() -> MagicMock:
    """Build a minimal mock config entry with just the entry_id this code path needs."""
    entry = MagicMock()
    entry.entry_id = "test-entry-id"
    return entry


async def test_bypass_without_explicit_partition_id_auto_resolves(hass, config_entry) -> None:
    """
    The actual crash from issue #80: bypass_sensor called with only resource_id, no partition_id.

    This must correctly iterate hub.api.partitions (not .values()) to
    find the matching partition by system_id.
    """
    sensor = _make_sensor(SYSTEM_ID)
    partition = _make_partition(PARTITION_ID, SYSTEM_ID)
    hub = _make_hub(sensors={RESOURCE_ID: sensor}, partitions=[partition])
    auto_off_manager = AutoOffManager(hass, config_entry.entry_id)

    _async_register_services(hass, config_entry, hub, auto_off_manager)

    await hass.services.async_call(
        DOMAIN, SERVICE_BYPASS_SENSOR, {ATTR_RESOURCE_ID: RESOURCE_ID}, blocking=True
    )

    hub.api.partitions.change_sensor_bypass.assert_called_once_with(
        PARTITION_ID, bypass_ids=[RESOURCE_ID], unbypass_ids=None
    )


async def test_unbypass_without_explicit_partition_id_auto_resolves(hass, config_entry) -> None:
    """Same auto-resolve path, via the unbypass service."""
    sensor = _make_sensor(SYSTEM_ID)
    partition = _make_partition(PARTITION_ID, SYSTEM_ID)
    hub = _make_hub(sensors={RESOURCE_ID: sensor}, partitions=[partition])
    auto_off_manager = AutoOffManager(hass, config_entry.entry_id)

    _async_register_services(hass, config_entry, hub, auto_off_manager)

    await hass.services.async_call(
        DOMAIN, SERVICE_UNBYPASS_SENSOR, {ATTR_RESOURCE_ID: RESOURCE_ID}, blocking=True
    )

    hub.api.partitions.change_sensor_bypass.assert_called_once_with(
        PARTITION_ID, bypass_ids=None, unbypass_ids=[RESOURCE_ID]
    )


async def test_bypass_with_explicit_partition_id_skips_auto_resolve(hass, config_entry) -> None:
    """An explicit partition_id is used directly, without needing to iterate partitions at all."""
    sensor = _make_sensor(SYSTEM_ID)
    # Deliberately no matching partition in the list - if auto-resolve were
    # incorrectly triggered anyway, this would fail with "no partition found".
    hub = _make_hub(sensors={RESOURCE_ID: sensor}, partitions=[])
    auto_off_manager = AutoOffManager(hass, config_entry.entry_id)

    _async_register_services(hass, config_entry, hub, auto_off_manager)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_BYPASS_SENSOR,
        {ATTR_RESOURCE_ID: RESOURCE_ID, ATTR_PARTITION_ID: PARTITION_ID},
        blocking=True,
    )

    hub.api.partitions.change_sensor_bypass.assert_called_once_with(
        PARTITION_ID, bypass_ids=[RESOURCE_ID], unbypass_ids=None
    )


async def test_bypass_unknown_resource_id_raises(hass, config_entry) -> None:
    """An unknown resource_id raises a clear, actionable error rather than a raw KeyError."""
    hub = _make_hub(sensors={}, partitions=[])
    auto_off_manager = AutoOffManager(hass, config_entry.entry_id)

    _async_register_services(hass, config_entry, hub, auto_off_manager)

    with pytest.raises(ServiceValidationError, match="No such Alarm\\.com sensor"):
        await hass.services.async_call(
            DOMAIN, SERVICE_BYPASS_SENSOR, {ATTR_RESOURCE_ID: "does-not-exist"}, blocking=True
        )


async def test_bypass_unsupported_sensor_raises(hass, config_entry) -> None:
    """A sensor that doesn't support bypass at all raises a clear error, not a silent no-op."""
    sensor = _make_sensor(SYSTEM_ID, supports_bypass=False)
    hub = _make_hub(sensors={RESOURCE_ID: sensor}, partitions=[])
    auto_off_manager = AutoOffManager(hass, config_entry.entry_id)

    _async_register_services(hass, config_entry, hub, auto_off_manager)

    with pytest.raises(ServiceValidationError, match="does not support bypass"):
        await hass.services.async_call(
            DOMAIN, SERVICE_BYPASS_SENSOR, {ATTR_RESOURCE_ID: RESOURCE_ID}, blocking=True
        )


async def test_bypass_no_matching_partition_raises(hass, config_entry) -> None:
    """When no partition matches the sensor's system_id, a clear error is raised rather than crashing."""
    sensor = _make_sensor(SYSTEM_ID)
    other_partition = _make_partition(PARTITION_ID, "some-other-system-id")
    hub = _make_hub(sensors={RESOURCE_ID: sensor}, partitions=[other_partition])
    auto_off_manager = AutoOffManager(hass, config_entry.entry_id)

    _async_register_services(hass, config_entry, hub, auto_off_manager)

    with pytest.raises(ServiceValidationError, match="No partition found"):
        await hass.services.async_call(
            DOMAIN, SERVICE_BYPASS_SENSOR, {ATTR_RESOURCE_ID: RESOURCE_ID}, blocking=True
        )
