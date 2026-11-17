"""JSON:API utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import humps

if TYPE_CHECKING:
    from _pyalarmdotcomajax.models.jsonapi import Link

###########################
# SCHEMA HELPER FUNCTOINS #
###########################


def page_number_from_link(link: Link | None | str) -> int | None:
    """
    Extract page number from links in a JSON:API response object.

    Returns page number if present, otherwise returns None.
    """

    return int(match.group(1)) if link and (match := re.search(r"page\[number\]=(\d+)", str(link))) else None


@dataclass
class CamelizerMixin:
    """Convert keys between snake_case and camelCase."""

    @classmethod
    def __pre_deserialize__(cls, d: dict[Any, Any]) -> dict[Any, Any]:
        """Pre-deserialization hook to convert keys from camelCase to snake case."""

        return humps.decamelize(d)

    def __post_serialize__(self, d: dict[Any, Any]) -> dict[Any, Any]:
        """Post-serialization hook to convert keys from snake_case to camelCase."""

        return humps.camelize(d)


def int_to_str(value: Any) -> str:
    """Convert an integer to a string during deserialization."""

    if isinstance(value, str | int):
        return str(value)

    raise ValueError
