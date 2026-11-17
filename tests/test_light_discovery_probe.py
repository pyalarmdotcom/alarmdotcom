"""Exercise the real system response parser and its count-only discovery probe."""

import json
import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from _pyalarmdotcomajax import AlarmBridge
from _pyalarmdotcomajax.controllers import AdcSuccessDocumentSingle
from _pyalarmdotcomajax.light_discovery import summarize_light_discovery

import custom_components.alarmdotcom  # noqa: F401

SYSTEM_ID = "private-system-marker"
LIGHT_ID = "private-light-marker"


def document(relationship):
    """Use deliberately recognizable fake secrets to detect accidental logging."""
    return {"data": {"id": SYSTEM_ID, "type": "systems/system", "attributes": {
        "description": "private-name-marker", "password": "private-password-marker",
    }, "relationships": {"lights": relationship}}}


@pytest.mark.parametrize("extra", [
    {}, {"meta": {"count": 1}}, {"links": {"related": "private-url-marker"}},
    {"meta": {"count": 1}, "links": {"related": "private-url-marker"}},
])
def test_valid_ids_survive_real_parser_with_metadata_and_links(extra):
    """Common combinations do not justify another speculative parser fix."""
    payload = document({"data": [{"id": LIGHT_ID, "type": "devices/light"}], **extra})
    parsed = AdcSuccessDocumentSingle.from_dict(payload)
    summary = summarize_light_discovery(payload, parsed.data, SYSTEM_ID)
    assert summary["raw_entries"] == summary["parsed_entries"] == 1
    assert summary["raw_and_parsed_ids_match"]
    assert summary["response_matches_requested_system"]
    for marker in (SYSTEM_ID, LIGHT_ID, "private-url-marker", "private-password-marker", "private-name-marker"):
        assert marker not in repr(summary)


@pytest.mark.parametrize(("relationship", "shape"), [
    ({"data": []}, "list"), ({"data": None}, "null"),
    ({"meta": {"count": 4}, "links": {"related": "private-url-marker"}}, "missing"),
])
def test_empty_and_link_only_responses_are_distinguishable(relationship, shape):
    """A valid relationship can advertise devices without embedding their IDs."""
    payload = document(relationship)
    parsed = AdcSuccessDocumentSingle.from_dict(payload)
    summary = summarize_light_discovery(payload, parsed.data, SYSTEM_ID)
    assert summary["raw_data_shape"] == shape
    assert summary["raw_entries"] == summary["parsed_entries"] == 0
    if shape == "missing":
        assert summary["related_link_present"]
        assert summary["declared_count"] == 4


def test_probe_detects_a_parser_loss_or_a_different_system():
    """Compare actual ID sets internally rather than reporting two equal counts."""
    payload = document({"data": [{"id": LIGHT_ID, "type": "devices/light"}]})
    parsed = AdcSuccessDocumentSingle.from_dict(document({"data": [{"id": "different-private-id", "type": "devices/light"}]}))
    summary = summarize_light_discovery(payload, parsed.data, "another-private-system")
    assert not summary["raw_and_parsed_ids_match"]
    assert not summary["response_matches_requested_system"]
    assert summary["raw_entries"] == summary["parsed_entries"] == 1


async def test_request_probe_does_not_forward_internal_flag_or_log_secrets(caplog):
    """Run the actual HTTP parsing path with a synthetic body and no network."""
    payload = document({"data": [{"id": LIGHT_ID, "type": "devices/light"}]})
    response = AsyncMock(status=200)
    response.text.return_value = json.dumps(payload)
    captured = []

    @asynccontextmanager
    async def fake_request(*args, **kwargs):
        captured.append(kwargs)
        yield response

    bridge = AlarmBridge()
    with patch.object(bridge, "create_request", side_effect=fake_request), caplog.at_level(logging.DEBUG):
        result = await bridge.request(
            "get", "https://example.test/system", success_response_class=AdcSuccessDocumentSingle,
            light_discovery_system_id=SYSTEM_ID,
        )
    assert result.data.id == SYSTEM_ID
    assert "light_discovery_system_id" not in captured[0]
    assert "'raw_entries': 1" in caplog.text
    assert "'parsed_entries': 1" in caplog.text
    for marker in (SYSTEM_ID, LIGHT_ID, "private-password-marker", "private-name-marker"):
        assert marker not in caplog.text


async def test_probe_failure_does_not_prevent_successful_discovery(caplog):
    """Even unexpected probe errors reveal only their type and do not fail setup."""
    payload = document({"data": []})
    response = AsyncMock(status=200)
    response.text.return_value = json.dumps(payload)

    @asynccontextmanager
    async def fake_request(*args, **kwargs):
        yield response

    bridge = AlarmBridge()
    with (
        patch.object(bridge, "create_request", side_effect=fake_request),
        patch("_pyalarmdotcomajax.summarize_light_discovery", side_effect=ValueError("private-exception-marker")),
        caplog.at_level(logging.DEBUG),
    ):
        result = await bridge.request(
            "get", "https://example.test/system", success_response_class=AdcSuccessDocumentSingle,
            light_discovery_system_id=SYSTEM_ID,
        )
    assert result.data.id == SYSTEM_ID
    assert "probe unavailable (ValueError)" in caplog.text
    assert "private-exception-marker" not in caplog.text


@pytest.mark.parametrize("count", [1, "1"])
def test_browser_numeric_ids_and_string_counts_are_normalized(count):
    """Match the real browser response's types using neutral synthetic IDs."""
    payload = document({"data": [{"id": "30001-1204", "type": "devices/light"}], "meta": {"count": count}})
    payload["data"]["id"] = 20001
    parsed = AdcSuccessDocumentSingle.from_dict(payload)
    summary = summarize_light_discovery(payload, parsed.data, "20001")
    assert parsed.data.id == "20001"
    assert summary["response_matches_requested_system"]
    assert summary["declared_count_present"]
    assert summary["declared_count"] == 1
    assert summary["raw_entries"] == summary["parsed_entries"] == 1
    assert summary["raw_and_parsed_ids_match"]


@pytest.mark.parametrize("count", ["private-metadata-marker", "100000000000000", True, -1, 1001])
def test_invalid_count_values_are_never_echoed(count):
    """Arbitrary metadata and booleans must not become logged numeric counts."""
    payload = document({"data": [], "meta": {"count": count}})
    parsed = AdcSuccessDocumentSingle.from_dict(payload)
    summary = summarize_light_discovery(payload, parsed.data, SYSTEM_ID)
    assert not summary["declared_count_present"]
    assert summary["declared_count"] == 0
    assert "private-metadata-marker" not in repr(summary)
