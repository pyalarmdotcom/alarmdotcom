"""Generic helper functions."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar, overload

from _pyalarmdotcomajax.models.jsonapi import Resource, ResourceIdentifier
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

if TYPE_CHECKING:
    from _pyalarmdotcomajax.models.base import AdcResource

log = logging.getLogger(__name__)


def get_related_entity_id_by_key(resource: Resource, name: str) -> str | None:
    """Return related entity ID by relationship dict key."""

    try:
        return resource.relationships.get(name).data.id
    except Exception:
        log.info("Unable to get related entity ID for %s in %s", name, resource.id)
        log.debug("Resource: %s", resource.to_json())

    return None


def get_all_related_entity_ids(resource: Resource) -> set[str]:
    """Return related entity ID by relationship dict key."""

    relations = set({})

    rel_items = resource.relationships or {}

    for rel_value in rel_items.values():
        if hasattr(rel_value, "data"):
            if isinstance(rel_value.data, ResourceIdentifier):
                relations.add(rel_value.data.id)
            if isinstance(rel_value.data, list):
                for item in rel_value.data:
                    if isinstance(item, ResourceIdentifier):
                        relations.add(item.id)

    return relations


def slug_to_title(slug: str) -> str:
    """Convert slug to title case."""

    return slug.replace("_", " ").title()


def dict_truncate(d: dict, max_length: int = 500) -> dict:
    """
    Recursively truncates string values in a dictionary (and nested dictionaries) to a maximum length.

    :param d: The dictionary to process.
    :param max_length: The maximum length of string values. Defaults to 500 characters.
    """
    for key, value in d.items():
        if isinstance(value, str) and len(value) > max_length:
            d[key] = (
                value[:max_length] + "...+" + str(len(value) - max_length)
            )  # Truncate the string
        elif isinstance(value, dict):
            dict_truncate(value, max_length)  # Recursively process nested dictionaries

    return d


T = TypeVar("T")


@overload
def cli_format(value: bool | Enum) -> str: ...


@overload
def cli_format(value: Any) -> Any: ...


def cli_format(value: T | Any) -> T | str | dict | list:
    """Format value for CLI output."""

    # Change Value

    if isinstance(value, Enum):
        value = value.name.title()

    if value is True:
        value = "√"

    if value is False:
        value = "X"

    # Truncate

    if isinstance(value, str) and len(value) > 100:
        value = value[:100] + "..."

    # Color

    if value in [
        "√",
        "Closed",
        "Locked",
        "Armed Stay",
        "Armed Night",
        "Armed Away",
        "On",
    ]:
        value = f"[green]{value!s}[/green]"
    elif value in ["X", "Open", "Unlocked", "Disarmed", "Off"]:
        value = f"[red]{value!s}[/red]"
    else:
        value = f"[grey50]{value!s}[/grey50]"

    return value


def resources_pretty(resource_type_str: str, resources: list[AdcResource]) -> Group:
    """Return Rich Panel or Table representation of resources in controller."""

    # Alphabetize list
    resources = sorted(
        resources,
        key=lambda x: str(
            x.api_resource.attributes.get("description", "Unnamed Resource")
        ),
    )

    def fmt_attr(x: Any, y: Any) -> Table:
        tbl = Table.grid(expand=True, padding=(0, 2))
        tbl.add_column(no_wrap=True, max_width=50)
        tbl.add_column(justify="right", max_width=50, no_wrap=True)
        tbl.add_row(f"[b]{slug_to_title(x)}[/b]", str(cli_format(y)))
        return tbl

    resource_type_banner = Panel(
        f"[black on white bold]{slug_to_title(resource_type_str).upper()}[/black on white bold]",
        border_style="black",
        style="black on white",
    )

    if len(resources) == 0:
        return Group("\n", resource_type_banner, "\nNone")

    formatted_resources = []

    for resource in resources:
        title_text = str(
            getattr(resource.attributes, "description", None)
            or getattr(
                resource.attributes,
                "name",
                f"Unnamed {slug_to_title(resource_type_str)}",
            )
        ).upper()

        resource_title = f"\n[underline bright_cyan][bold]{title_text}[/bold] ({resource.id})[/underline bright_cyan]"

        resource_attributes = [
            fmt_attr("state", getattr(resource.attributes, "state", "[i]No State[/i]"))
        ]

        for key, value in sorted(asdict(resource.attributes).items()):
            if key not in ["description", "state"]:
                resource_attributes.append(fmt_attr(key, value))

        formatted_resources.append(
            Group(
                resource_title, Columns(resource_attributes, padding=(0, 2), equal=True)
            )
        )

    return Group("\n", resource_type_banner, *formatted_resources)


def resources_raw(
    resource_type_str: str, resources: list[Resource | AdcResource]
) -> Group:
    """Return raw JSON for all controller resources."""

    # Alphabetize list
    resources = sorted(
        resources,
        key=lambda x: str(
            x.attributes.get("description", "Unnamed Resource")
            if isinstance(x, Resource)
            else x.api_resource.attributes.get("description", "Unnamed Resource")
        ),
    )

    resource_title = (
        f"[bold bright_white on yellow]\n\n===[ {slug_to_title(resource_type_str)} ]==="
    )

    if len(resources) == 0:
        return Group(resource_title, "\nNone")

    output = [
        Group(
            "\n[bright_white underline]"
            + (
                str(resource.attributes.get("description", "Unnamed Resource"))
                if isinstance(resource, Resource)
                else getattr(
                    resource.attributes,
                    "description",
                    f"Unnamed {slug_to_title(resource_type_str)}",
                )
            ).upper(),
            Syntax(
                str(
                    resource.to_json()
                    if isinstance(resource, Resource)
                    else json.dumps(dict_truncate(resource.api_resource.to_dict()))
                ),
                "JSON",
                word_wrap=True,
            ),
        )
        for resource in resources
    ]

    return Group(resource_title, *output)
