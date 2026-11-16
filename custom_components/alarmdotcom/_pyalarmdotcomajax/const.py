"""Shared constants."""

from __future__ import annotations

from enum import Enum

# CONFIG: BEGIN
REQUEST_RETRY_LIMIT = 3
SUBMIT_RETRY_LIMIT = 2
DEBUG_REQUEST_DUMP_MAX_LEN = 1000
# CONFIG: END


# URLS: BEGIN
URL_BASE = "https://www.alarm.com/"
API_URL_BASE = URL_BASE + "web/api/"

ATTR_STATE = "state"
ATTR_DESIRED_STATE = "desiredState"
# URLS: END


class ResponseTypes(Enum):
    """Response types."""

    JSON = {"Accept": "application/json", "charset": "utf-8"}  # noqa: RUF012
    JSONAPI = {"Accept": "application/vnd.api+json", "charset": "utf-8"}  # noqa: RUF012
    FORM = {"Content-Type": "application/x-www-form-urlencoded", "charset": "utf-8"}  # noqa: RUF012
    HTML = {"Accept": "text/html,application/xhtml+xml,application/xml"}  # noqa: RUF012
