"""Service teardown on unload, against a sibling entry that is not loaded."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alarmdotcom import async_unload_entry
from custom_components.alarmdotcom.access_service import (
    SERVICE_GET_TEMPORARY_USER_SCHEDULE,
    SERVICE_SET_TEMPORARY_ACCESS,
)
from custom_components.alarmdotcom.const import DOMAIN, SERVICE_BYPASS_SENSOR


def _loaded_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Build a config entry in the state async_unload_entry expects to find it in."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="Alarm.com")
    entry.add_to_hass(hass)
    hub = MagicMock()
    hub.close = AsyncMock(return_value=True)
    runtime = MagicMock()
    runtime.hub = hub
    runtime.camera_session = None
    runtime.auto_off_manager.async_unload = AsyncMock(return_value=None)
    runtime.activity_feed_tracker.async_stop = MagicMock(return_value=None)
    entry.runtime_data = runtime
    return entry


async def test_services_are_removed_when_the_last_loaded_entry_unloads(
    hass: HomeAssistant,
) -> None:
    """The ordinary case: nothing else is loaded, so the services must go."""
    entry = _loaded_entry(hass)
    hass.services.async_register(DOMAIN, SERVICE_BYPASS_SENSOR, AsyncMock())
    hass.services.async_register(DOMAIN, SERVICE_SET_TEMPORARY_ACCESS, AsyncMock())
    hass.services.async_register(DOMAIN, SERVICE_GET_TEMPORARY_USER_SCHEDULE, AsyncMock())

    with patch.object(hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)):
        await async_unload_entry(hass, entry)

    assert not hass.services.has_service(DOMAIN, SERVICE_BYPASS_SENSOR)
    assert not hass.services.has_service(DOMAIN, SERVICE_SET_TEMPORARY_ACCESS)
    assert not hass.services.has_service(DOMAIN, SERVICE_GET_TEMPORARY_USER_SCHEDULE)


async def test_a_disabled_sibling_must_not_keep_the_services_registered(
    hass: HomeAssistant,
) -> None:
    """
    A disabled entry has no hub, so it cannot serve the services it keeps alive.

    The teardown counts hass.config_entries.async_entries(DOMAIN), which defaults
    to include_disabled=True and include_ignore=True. So a disabled sibling makes
    `remaining` non-empty and the services survive - closed over the hub that
    async_unload_entry has just closed one line above.
    """
    entry = _loaded_entry(hass)
    disabled = MockConfigEntry(
        domain=DOMAIN, data={}, title="Old account", disabled_by=ConfigEntryDisabler.USER
    )
    disabled.add_to_hass(hass)

    hass.services.async_register(DOMAIN, SERVICE_BYPASS_SENSOR, AsyncMock())
    hass.services.async_register(DOMAIN, SERVICE_SET_TEMPORARY_ACCESS, AsyncMock())
    hass.services.async_register(DOMAIN, SERVICE_GET_TEMPORARY_USER_SCHEDULE, AsyncMock())

    with patch.object(hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)):
        await async_unload_entry(hass, entry)

    assert not hass.services.has_service(DOMAIN, SERVICE_BYPASS_SENSOR), (
        "the only loaded entry is gone, so nothing can serve alarmdotcom.bypass_sensor"
    )
