"""
Count-only probes for the system relationship involved in light discovery.

The normal HTTP logger deliberately omits payloads. These probes reduce one
system response to predefined shapes, counts, and equality checks, so we can
compare the wire format with the parsed model without dumping personal data.
"""

from __future__ import annotations

from typing import Any

from _pyalarmdotcomajax.models.jsonapi import Resource


def _shape(value: object, *, present: bool = True) -> str:
    """Use a fixed vocabulary, never a value or a caller-provided field name."""
    if not present:
        return "missing"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return "unexpected"


def _resource_id(value: object) -> str | None:
    """Normalize numeric JSON IDs in memory, without ever returning them in logs."""
    if type(value) is int:
        return str(value)
    if isinstance(value, str) and value.strip():
        return value
    return None


def summarize_light_discovery(
    payload: object, parsed: Resource | list[Resource], requested_system_id: str,
) -> dict[str, Any]:
    """Compare raw and parsed light IDs in memory, returning only safe metadata."""
    data = payload.get("data") if isinstance(payload, dict) else None
    systems = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    raw_ids: set[str] = set()
    raw_entries = 0
    shapes: set[str] = set()
    related_link_present = False
    declared_count = 0
    declared_count_present = False
    response_matches_request = False
    for system in systems:
        if not isinstance(system, dict):
            continue
        response_matches_request |= _resource_id(system.get("id")) == requested_system_id
        relationships = system.get("relationships")
        light = relationships.get("lights") if isinstance(relationships, dict) else None
        if not isinstance(light, dict):
            shapes.add("missing" if light is None else "unexpected")
            continue
        light_data = light.get("data")
        shapes.add(_shape(light_data, present="data" in light))
        entries = light_data if isinstance(light_data, list) else [light_data] if isinstance(light_data, dict) else []
        raw_entries += len(entries)
        for item in entries:
            if isinstance(item, dict) and (identifier := _resource_id(item.get("id"))) is not None:
                raw_ids.add(identifier)
        links = light.get("links")
        related_link_present |= isinstance(links, dict) and "related" in links
        meta = light.get("meta")
        count = meta.get("count") if isinstance(meta, dict) else None
        # Metadata count is useful for detecting a link-only relationship. Never
        # echo arbitrary metadata values, strings, names, or unusually large numbers.
        if isinstance(count, str) and len(count) <= 4 and count.isascii() and count.isdecimal():
            count = int(count)
        if type(count) is int and 0 <= count <= 1000:
            declared_count_present = True
            declared_count += count
    parsed_systems = parsed if isinstance(parsed, list) else [parsed]
    parsed_ids: set[str] = set()
    parsed_entries = 0
    for system in parsed_systems:
        relationship = (system.relationships or {}).get("lights")
        if relationship is not None:
            parsed_entries += len(relationship.data_list)
            parsed_ids.update(item.id for item in relationship.data_list
                              if isinstance(item.id, str) and item.id.strip())
    return {
        "response_system_count": len(systems),
        "response_matches_requested_system": response_matches_request,
        "raw_data_shape": ",".join(sorted(shapes)) or "missing",
        "raw_entries": raw_entries,
        "raw_usable_id_count": len(raw_ids),
        "parsed_entries": parsed_entries,
        "parsed_usable_id_count": len(parsed_ids),
        "raw_and_parsed_ids_match": raw_ids == parsed_ids,
        "related_link_present": related_link_present,
        "declared_count_present": declared_count_present,
        "declared_count": declared_count,
    }
