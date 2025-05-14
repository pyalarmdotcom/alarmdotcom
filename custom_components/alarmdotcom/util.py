"""Utility functions."""

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def slug_to_title(slug: str) -> str:
    """Convert slug to title case."""

    return slug.replace("_", " ").title()


async def cleanup_orphaned_entities_and_devices(
    hass: "HomeAssistant",
    config_entry: "ConfigEntry",
    current_entity_ids: set[str],
    current_unique_ids: set[str],
    platform: str,
) -> None:
    """
    Remove orphaned entities and devices for a given platform.

    Args:
        hass: HomeAssistant instance
        config_entry: The config entry for the integration
        current_entity_ids: Set of entity_ids currently provided by the integration
        current_unique_ids: Set of unique_ids currently provided by the integration
        platform: The Home Assistant platform (e.g., "light", "lock", "cover", etc.)

    """
    entity_registry = async_get_entity_registry(hass)
    device_registry = async_get_device_registry(hass)

    # Remove orphaned entities for this platform, including those with no unique_id
    for entry in list(entity_registry.entities.values()):
        if (
            entry.config_entry_id == config_entry.entry_id
            and entry.domain == platform
            and (
                entry.entity_id not in current_entity_ids
                and (entry.unique_id not in current_unique_ids or not entry.unique_id)
            )
        ):
            entity_registry.async_remove(entry.entity_id)

    # Remove orphaned devices with no entities left, but skip SERVICE devices
    for device in list(device_registry.devices.values()):
        if (
            device.config_entries == {config_entry.entry_id}
            and device.entry_type != DeviceEntryType.SERVICE
        ):
            device_entities = [
                e for e in entity_registry.entities.values() if e.device_id == device.id
            ]
            # No entities at all
            if not device_entities or all(
                e.domain == platform and not e.unique_id for e in device_entities
            ):
                device_registry.async_remove_device(device.id)
