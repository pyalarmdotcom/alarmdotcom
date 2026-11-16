"""JSON:API custom types."""

import re
from typing import Self

from mashumaro.types import SerializableType

#######
# URI #
#######


class URI(str):
    """
    Create a URI object from a string.

    Used to satisfy mypy's strict type checking.
    Based on regex in Appendix B of RFC3986 (https://www.rfc-editor.org/rfc/rfc3986#appendix-B)
    """

    match: re.Match

    def __new__(cls, s: str) -> Self:
        """Create a new URL object from a string."""

        pattern = r"^(([^:\/?#]+):)?(\/\/([^\/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?"

        if not (match := re.match(pattern, s)):
            raise TypeError(f"{s} is not a valid URL")

        url = super().__new__(cls, s)
        url.match = match

        return url

    def __str__(self) -> str:
        """Return the URL as a string."""

        return self.match.string if isinstance(self.match.string, str) else ""

    @property
    def scheme(self) -> str:
        """Return the URL scheme."""

        return self.match.group(2) or ""

    @property
    def authority(self) -> str:
        """Return the URL authority."""

        return self.match.group(4) or ""

    @property
    def path(self) -> str:
        """Return the URL path."""

        return self.match.group(5) or ""

    @property
    def query(self) -> str:
        """Return the URL query."""

        return self.match.group(7) or ""

    @property
    def fragment(self) -> str:
        """Return the URL fragment."""

        return self.match.group(9) or ""


class RangeInt(int, SerializableType):
    """Create an int object with a range validation."""

    __min_value__: int
    __max_value__: int

    def __new__(cls, value: int, *, min_value: int | None = None, max_value: int | None = None) -> "RangeInt":
        """Create a new RangeInt object."""
        if min_value is not None:
            cls.__min_value__ = min_value
        if max_value is not None:
            cls.__max_value__ = max_value
        if not (cls.__min_value__ <= value <= cls.__max_value__):
            raise ValueError(f"Value {value} is not within the range {cls.__min_value__} to {cls.__max_value__}")
        return int.__new__(cls, value)

    @classmethod
    def _deserialize(cls, value: int) -> "RangeInt":
        return cls(value, min_value=cls.__min_value__, max_value=cls.__max_value__)


class LedColor(SerializableType):
    """Represents an LED color with serialization and deserialization from/to HEX format."""

    def __init__(self, hex: str | None = None, rgb: tuple[int, int, int] | None = None) -> None:
        """Initialize with either HEX or RGB format."""
        if hex:
            self.hex = self._validate_and_format_hex(hex)
        elif rgb:
            self.hex = self._rgb_to_hex(rgb)
        else:
            raise ValueError("Must initialize with either hex or rgb")

    @classmethod
    def _deserialize(cls, value: str) -> "LedColor":
        """Deserialize from HEX format."""
        return cls(hex=value)

    def _serialize(self) -> str:
        """Serialize to HEX format."""
        return self.hex

    @staticmethod
    def _validate_and_format_hex(value: str) -> str:
        """Validate and format the HEX value."""
        match = re.match(r"^#?([0-9a-fA-F]{6})$", value)
        if not match:
            raise ValueError("Invalid HEX color format")
        return f"#{match.group(1).upper()}"

    @staticmethod
    def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
        """Convert RGB format to HEX."""
        return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

    @property
    def rgb(self) -> tuple[int, int, int]:
        """Return the color as an RGB tuple."""

        r, g, b = (int(self.hex[i : i + 2], 16) for i in (1, 3, 5))

        return (r, g, b)  # Explicitly return a tuple of three integers to satisfy mypy
