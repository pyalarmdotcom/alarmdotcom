"""
Tests for AlarmBridge.get_activity_history (_pyalarmdotcomajax/__init__.py).

Mocks only self.get (the underlying HTTP call, already exercised
throughout the rest of this library) - these tests focus on what's
actually new here: correct request parameter construction against the
real confirmed request shape, and correctly filtering the response's
`included` array down to just activity/history-event resources.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from custom_components.alarmdotcom._pyalarmdotcomajax import AlarmBridge
from custom_components.alarmdotcom._pyalarmdotcomajax.models.jsonapi import Resource


def _make_mock_response(included: list[Resource]) -> MagicMock:
    """Build a mock AdcSuccessDocumentMulti-shaped response."""
    response = MagicMock()
    response.included = included
    return response


async def test_request_params_match_the_confirmed_real_shape() -> None:
    """
    The request is built with exactly the parameters confirmed from a real captured request.

    https://www.alarm.com/web/api/activity/activityDays?debounceTimeMs=1000&endTime=&
    page=1&pageSize=100&searchString=&showOnlyOpenEyeEvents=false&startTime=... -
    captured directly from the Alarm.com web app's own Activity page network traffic
    (GitHub issue #79's investigation), not guessed from other endpoints' conventions.
    """
    mock_self = MagicMock(spec=AlarmBridge)
    mock_self.get = AsyncMock(return_value=_make_mock_response([]))

    start_time = datetime(2026, 7, 7, 4, 13, 7, tzinfo=UTC)
    await AlarmBridge.get_activity_history(mock_self, start_time=start_time)

    mock_self.get.assert_called_once()
    call_args = mock_self.get.call_args
    assert call_args.args[0] == "activity/activityDays"
    assert call_args.args[1] is None
    params = call_args.kwargs["params"]
    assert params["debounceTimeMs"] == "1000"
    assert params["startTime"] == "2026-07-07T04:13:07.000Z"
    assert params["endTime"] == ""
    assert params["page"] == "1"
    assert params["pageSize"] == "100"
    assert params["searchString"] == ""
    assert params["showOnlyOpenEyeEvents"] == "false"


async def test_end_time_is_formatted_when_provided() -> None:
    """When end_time is given, it's formatted the same way as start_time, not left blank."""
    mock_self = MagicMock(spec=AlarmBridge)
    mock_self.get = AsyncMock(return_value=_make_mock_response([]))

    start_time = datetime(2026, 7, 7, 4, 13, 7, tzinfo=UTC)
    end_time = datetime(2026, 7, 8, 0, 0, 0, tzinfo=UTC)
    await AlarmBridge.get_activity_history(mock_self, start_time=start_time, end_time=end_time)

    params = mock_self.get.call_args.kwargs["params"]
    assert params["endTime"] == "2026-07-08T00:00:00.000Z"


async def test_page_and_page_size_are_passed_through() -> None:
    """Custom page/page_size arguments actually reach the request, for pagination."""
    mock_self = MagicMock(spec=AlarmBridge)
    mock_self.get = AsyncMock(return_value=_make_mock_response([]))

    await AlarmBridge.get_activity_history(
        mock_self, start_time=datetime(2026, 7, 7, tzinfo=UTC), page=3, page_size=50
    )

    params = mock_self.get.call_args.kwargs["params"]
    assert params["page"] == "3"
    assert params["pageSize"] == "50"


async def test_returns_only_history_event_resources_from_included() -> None:
    """
    The response's included array is filtered to just activity/history-event resources.

    Defensive, not just theoretical: real captured responses show other
    resource types can appear in relationships (e.g. video/video-event
    for camera-triggered events) - this confirms those wouldn't
    accidentally get treated as HistoryEvent objects if they ever showed
    up in `included` directly.
    """
    history_event_resource = Resource(
        id="M-123",
        type="activity/history-event",
        attributes={"description": "Unlocked by Chris Pulliam", "eventTypeName": "DoorUnlocked"},
    )
    unrelated_resource = Resource(id="177774090884", type="video/video-event", attributes={})

    mock_self = MagicMock(spec=AlarmBridge)
    mock_self.get = AsyncMock(return_value=_make_mock_response([history_event_resource, unrelated_resource]))

    events = await AlarmBridge.get_activity_history(mock_self, start_time=datetime(2026, 7, 7, tzinfo=UTC))

    # Deliberately not isinstance(events[0], HistoryEvent): this library's
    # code runs via a bare `_pyalarmdotcomajax` import (the sys.path shim
    # every other file in this integration also relies on), while this
    # test file imports the same class via the fully-qualified
    # `custom_components.alarmdotcom._pyalarmdotcomajax` path - Python
    # treats those as two distinct classes, so isinstance() would fail
    # here even though filtering worked correctly. Asserting on the
    # actual parsed content is both more robust and closer to what this
    # test is really checking: that the unrelated video/video-event
    # resource got filtered out, and the real history event's data came
    # through intact.
    assert len(events) == 1
    assert events[0].id == "M-123"
    assert events[0].attributes.event_type_name == "DoorUnlocked"


async def test_empty_included_returns_empty_list() -> None:
    """No events in range returns an empty list, not an error."""
    mock_self = MagicMock(spec=AlarmBridge)
    mock_self.get = AsyncMock(return_value=_make_mock_response([]))

    events = await AlarmBridge.get_activity_history(mock_self, start_time=datetime(2026, 7, 7, tzinfo=UTC))

    assert events == []
