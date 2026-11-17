"""
Device registry usage, held to the APIs that survive HA Core 2027.

Three deprecations were reported in #101, all of them on paths this integration
takes on every setup:

* ``DeviceInfo["via_device"]`` — the identifier-tuple form of the parent link,
  removed in HA Core 2027.8 in favour of ``via_device_id`` (a registry id);
* ``DeviceRegistry.async_get_device(identifiers=...)`` — ambiguous across config
  entries, superseded by ``async_get_device_by_identifier``;
* ``device_registry.devices`` used as a mapping — removed in HA Core 2027.9.

The last one is not merely a warning on current betas: it raises. These tests
assert the shape of what we emit and the helpers we call, so a regression fails
here rather than in a user's log.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alarmdotcom.button import _device_exists_in_registry
from custom_components.alarmdotcom.const import DOMAIN
from custom_components.alarmdotcom.entity import device_info_fn
from custom_components.alarmdotcom.util import cleanup_orphaned_entities_and_devices


@pytest.fixture
def hub(hass: HomeAssistant) -> MagicMock:
    """Build a hub whose registry-facing surface is real: hass and a live config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="Alarm.com")
    entry.add_to_hass(hass)

    hub = MagicMock()
    hub.hass = hass
    hub.config_entry = entry
    hub.api.active_system.id = "system-1"
    hub.api.partitions.get_device_partition.return_value = None
    return hub


def _register(hass: HomeAssistant, entry_id: str, resource_id: str) -> dr.DeviceEntry:
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(DOMAIN, resource_id)},
        name=resource_id,
    )


def _managed(hub: MagicMock, resource_id: str, *, system_id: str | None = None) -> None:
    resource = MagicMock()
    resource.id = resource_id
    resource.name = resource_id
    resource.system_id = system_id
    resource.attributes.mac_address = None
    resource.attributes.manufacturer = None
    resource.attributes.device_model = None
    hub.api.managed_devices = {resource_id: resource}


def test_parent_link_is_a_registry_id_not_an_identifier_tuple(hass: HomeAssistant, hub: MagicMock) -> None:
    """The link must be published as via_device_id, carrying the parent's registry id."""
    parent = _register(hass, hub.config_entry.entry_id, "system-1")
    _managed(hub, "sensor-1", system_id="system-1")

    info = device_info_fn(hub, "sensor-1", None)

    assert "via_device" not in info, "via_device is removed in HA Core 2027.8"
    assert info["via_device_id"] == parent.id
    # the registry id is not the Alarm.com resource id — a swap would silently unlink
    assert info["via_device_id"] != "system-1"


def test_no_parent_link_when_the_parent_was_never_registered(hass: HomeAssistant, hub: MagicMock) -> None:
    """An unregistered parent must produce no link at all, not a dangling one."""
    _managed(hub, "sensor-1", system_id="system-1")

    info = device_info_fn(hub, "sensor-1", None)

    assert "via_device_id" not in info
    assert "via_device" not in info


def test_the_system_device_is_not_linked_to_itself(hass: HomeAssistant, hub: MagicMock) -> None:
    """The system is the root of the tree, so it must not be given a parent."""
    _register(hass, hub.config_entry.entry_id, "system-1")
    _managed(hub, "system-1", system_id="system-1")

    info = device_info_fn(hub, "system-1", None)

    assert "via_device_id" not in info


def test_partition_is_preferred_over_system_as_the_parent(hass: HomeAssistant, hub: MagicMock) -> None:
    """A registered partition is the nearer parent and wins over the system."""
    _register(hass, hub.config_entry.entry_id, "system-1")
    partition = _register(hass, hub.config_entry.entry_id, "partition-1")
    hub.api.partitions.get_device_partition.return_value = "partition-1"
    _managed(hub, "sensor-1", system_id="system-1")

    info = device_info_fn(hub, "sensor-1", None)

    assert info["via_device_id"] == partition.id


def test_parent_lookup_ignores_an_identical_identifier_on_another_entry(hass: HomeAssistant, hub: MagicMock) -> None:
    """
    Identifiers are unique per entry, not globally.

    A second Alarm.com account registering the same resource id must not become
    the parent — which is exactly the ambiguity async_get_device carried and
    async_get_device_by_identifier removes.
    """
    other = MockConfigEntry(domain=DOMAIN, data={}, title="Second account")
    other.add_to_hass(hass)
    _register(hass, other.entry_id, "system-1")
    _managed(hub, "sensor-1", system_id="system-1")

    info = device_info_fn(hub, "sensor-1", None)

    assert "via_device_id" not in info


def test_device_exists_in_registry_is_scoped_to_this_entry(hass: HomeAssistant, hub: MagicMock) -> None:
    """The scan this replaced saw every device, so a second account counted as ours."""
    other = MockConfigEntry(domain=DOMAIN, data={}, title="Second account")
    other.add_to_hass(hass)
    _register(hass, other.entry_id, "elsewhere")
    _register(hass, hub.config_entry.entry_id, "here")

    assert _device_exists_in_registry(hub, "here") is True
    assert _device_exists_in_registry(hub, "elsewhere") is False
    assert _device_exists_in_registry(hub, "never-created") is False


async def test_platform_cleanup_does_not_remove_devices_from_other_platforms(
    hass: HomeAssistant,
) -> None:
    """A per-platform sweep must not remove another platform's devices (#136)."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="Alarm.com")
    entry.add_to_hass(hass)
    other = MockConfigEntry(domain=DOMAIN, data={}, title="Second account")
    other.add_to_hass(hass)

    registry = dr.async_get(hass)
    ours_orphan = _register(hass, entry.entry_id, "ours-orphan")
    ours_live = _register(hass, entry.entry_id, "ours-live")
    theirs_orphan = _register(hass, other.entry_id, "theirs-orphan")

    entity_registry = er.async_get(hass)
    live = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "ours-live-sensor", config_entry=entry, device_id=ours_live.id
    )

    await cleanup_orphaned_entities_and_devices(
        hass, entry, {live.entity_id}, {"ours-live-sensor"}, "sensor"
    )

    # Device cleanup cannot happen safely before all platforms have loaded.
    assert registry.async_get(ours_orphan.id) is not None
    assert registry.async_get(ours_live.id) is not None
    assert registry.async_get(theirs_orphan.id) is not None
    assert entity_registry.async_get(live.entity_id) is not None
