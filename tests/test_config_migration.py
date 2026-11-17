"""Check stored entry upgrades without requiring a working legacy installation."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alarmdotcom import async_migrate_entry
from custom_components.alarmdotcom.config_flow import ADCFlowHandler
from custom_components.alarmdotcom.const import (
    CONF_ARM_AWAY,
    CONF_ARM_HOME,
    CONF_ARM_NIGHT,
    DOMAIN,
)


@pytest.mark.parametrize("stored_version", [1, 2, 3, 4, 5])
async def test_legacy_entry_migrates_and_loads_again(hass: HomeAssistant, stored_version: int) -> None:
    """Preserve entry/registry identity and credentials through migration and reload."""
    data = {"username": "test@example.com", "password": "example", "2fa_cookie": "test-cookie"}
    options = {
        "arm_code": "1234",
        "update_interval": 30,
        "ws_reconnect_timeout": 15,
    }
    if stored_version <= 2:
        options.update({
            "use_arm_code": True,
            "force_bypass": "Always",
            "silent_arming": "Always",
            "no_entry_delay": "Always",
        })
    else:
        values = ["bypass", "silent"] if stored_version == 3 else ["force_bypass", "silent_arming"]
        options.update({mode: list(values) for mode in (CONF_ARM_HOME, CONF_ARM_AWAY, CONF_ARM_NIGHT)})
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="Legacy System:example", title="Legacy System",
        data=data, options=options, version=stored_version,
    )
    entry.add_to_hass(hass)
    entry_id = entry.entry_id
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "alarm_control_panel", DOMAIN, "test-system-1",
        suggested_object_id="existing_alarm", config_entry=entry,
    )
    entity_id = entity.entity_id

    assert await async_migrate_entry(hass, entry)
    assert entry.version == ADCFlowHandler.VERSION == 5
    assert entry.entry_id == entry_id
    assert entry.unique_id == "Legacy System:example"
    assert entry.data == data
    assert entry.options["arm_code"] == "1234"
    for mode in (CONF_ARM_HOME, CONF_ARM_AWAY, CONF_ARM_NIGHT):
        assert set(entry.options[mode]) == {"force_bypass", "silent_arming"}
    if stored_version < 5:
        assert "update_interval" not in entry.options
        assert "ws_reconnect_timeout" not in entry.options
    assert registry.async_get(entity_id).unique_id == "test-system-1"
    assert registry.async_get(entity_id).config_entry_id == entry_id

    # A migration must not leave an entry newer than the declared flow schema.
    # HA rejects such entries before setup on a subsequent restart/reload.
    migrated_options = deepcopy(dict(entry.options))
    with patch("custom_components.alarmdotcom.async_setup_entry", return_value=True) as setup:
        assert await hass.config_entries.async_setup(entry_id)
        setup.assert_awaited_once()
    assert await async_migrate_entry(hass, entry)
    assert dict(entry.options) == migrated_options
