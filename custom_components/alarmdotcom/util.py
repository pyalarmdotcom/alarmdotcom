"""Utility functions."""

from typing import TYPE_CHECKING

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

    # Remove orphaned entities for this platform.
    # An entity is orphaned when NEITHER its entity_id NOR its unique_id is
    # present in the current set. Entities without a unique_id are matched
    # solely by entity_id — we must not delete them just because unique_id is absent.
    for entry in list(entity_registry.entities.values()):
        if entry.config_entry_id != config_entry.entry_id or entry.domain != platform:
            continue

        matched_by_entity_id = entry.entity_id in current_entity_ids
        matched_by_unique_id = bool(entry.unique_id) and entry.unique_id in current_unique_ids

        if not matched_by_entity_id and not matched_by_unique_id:
            entity_registry.async_remove(entry.entity_id)

    # Device removal must not run from individual platform setup. During a
    # reload, other platforms may not have registered their entities yet.
    # Defer cross-platform device pruning until a complete inventory is known.
