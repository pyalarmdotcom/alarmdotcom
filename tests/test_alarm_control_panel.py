"""
Tests for alarm_control_panel.py's control_fn arm-code validation.

Covers a real bug found and fixed while clearing the pre-commit backlog:
HA core's _attr_code_format/_attr_code_arm_required only validates that an
entered code matches the expected *format* (numeric vs text) before
control_fn is called - it never checks the code against the actually
configured arm_code. Without the check added here, any correctly-formatted
code would succeed, defeating the point of configuring an arm code at all.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.alarmdotcom.alarm_control_panel import ARM_AWAY, DISARM, control_fn
from custom_components.alarmdotcom.const import CONF_ARM_CODE


def _make_hub(arm_code: str | None) -> MagicMock:
    """Build a mock hub with the given configured arm code (or none)."""
    hub = MagicMock()
    hub.config_entry.options = {CONF_ARM_CODE: arm_code} if arm_code else {}
    return hub


def _make_controller() -> MagicMock:
    """Build a mock partition controller with awaitable arm/disarm methods."""
    controller = MagicMock()
    controller.disarm = AsyncMock(return_value=None)
    controller.arm_away = AsyncMock(return_value=None)
    return controller


async def test_no_configured_code_allows_any_input() -> None:
    """With no arm code configured, commands succeed regardless of the code field."""
    hub = _make_hub(arm_code=None)
    controller = _make_controller()

    await control_fn(hub, controller, "partition-1", DISARM, {"code": "anything"})

    controller.disarm.assert_awaited_once_with("partition-1")


async def test_correct_code_succeeds() -> None:
    """The command proceeds when the entered code matches the configured one."""
    hub = _make_hub(arm_code="1234")
    controller = _make_controller()

    await control_fn(hub, controller, "partition-1", DISARM, {"code": "1234"})

    controller.disarm.assert_awaited_once_with("partition-1")


async def test_wrong_code_is_rejected() -> None:
    """
    An incorrect code raises instead of silently succeeding.

    This is the core regression test: before the fix, arm_code and the
    entered code were both computed and then never compared, so this
    would have incorrectly succeeded.
    """
    hub = _make_hub(arm_code="1234")
    controller = _make_controller()

    with pytest.raises(ServiceValidationError):
        await control_fn(hub, controller, "partition-1", DISARM, {"code": "0000"})

    controller.disarm.assert_not_awaited()


async def test_missing_code_is_rejected_when_one_is_configured() -> None:
    """Omitting the code field entirely is treated the same as a wrong code."""
    hub = _make_hub(arm_code="1234")
    controller = _make_controller()

    with pytest.raises(ServiceValidationError):
        await control_fn(hub, controller, "partition-1", ARM_AWAY, {})

    controller.arm_away.assert_not_awaited()
