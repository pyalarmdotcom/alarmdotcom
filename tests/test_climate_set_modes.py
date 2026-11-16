"""
Thermostat mode setters, held against the zero-valued enum member.

ThermostatFanMode and ThermostatState are IntEnums whose first real member is 0
(ThermostatFanMode.AUTO). The setters looked their argument up in a dict and
gated the API call on the RESULT'S TRUTHINESS, so "auto" resolved correctly,
evaluated false, and the function returned without calling the API and without
raising - an automation that fires, reports success, and never reaches the
thermostat (#99).

These tests pin the two properties that matter: a supported mode reaches the
API, and an unsupported one does not.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.climate import FAN_AUTO, FAN_ON, HVACMode

from custom_components.alarmdotcom import _pyalarmdotcomajax as pyadc
from custom_components.alarmdotcom.climate import set_fan_mode_fn, set_hvac_mode_fn

FAN_CIRCULATE = "circulate"


@pytest.fixture
def controller() -> MagicMock:
    """Build a thermostat controller whose set_state records what it was asked for."""
    c = MagicMock()
    c.set_state = AsyncMock(return_value=None)
    c.get.return_value.supported_fan_durations = [0, 60, 180]
    return c


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        (FAN_AUTO, pyadc.thermostat.ThermostatFanMode.AUTO),
        (FAN_ON, pyadc.thermostat.ThermostatFanMode.ON),
        (FAN_CIRCULATE, pyadc.thermostat.ThermostatFanMode.CIRCULATE),
    ],
)
async def test_every_supported_fan_mode_reaches_the_api(
    controller: MagicMock, requested: str, expected: object
) -> None:
    """AUTO is 0 and was dropped by a truthiness test; all three must call out."""
    await set_fan_mode_fn(controller, "thermostat-1", requested)

    controller.set_state.assert_awaited_once_with(
        "thermostat-1", fan_mode=expected, fan_mode_duration=0
    )


async def test_unknown_fan_mode_does_not_call_the_api(controller: MagicMock) -> None:
    """A mode this integration does not map must not reach the API at all."""
    await set_fan_mode_fn(controller, "thermostat-1", "turbo")

    controller.set_state.assert_not_awaited()


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        (HVACMode.OFF, pyadc.thermostat.ThermostatState.OFF),
        (HVACMode.HEAT, pyadc.thermostat.ThermostatState.HEAT),
        (HVACMode.COOL, pyadc.thermostat.ThermostatState.COOL),
        (HVACMode.HEAT_COOL, pyadc.thermostat.ThermostatState.AUTO),
    ],
)
async def test_every_supported_hvac_mode_reaches_the_api(
    controller: MagicMock, requested: HVACMode, expected: object
) -> None:
    """Same gate one function above; correct today only because OFF is 1."""
    await set_hvac_mode_fn(controller, "thermostat-1", requested)

    controller.set_state.assert_awaited_once_with("thermostat-1", state=expected)


async def test_unknown_hvac_mode_does_not_call_the_api(controller: MagicMock) -> None:
    """HVACMode.DRY is not in the map and must be dropped."""
    await set_hvac_mode_fn(controller, "thermostat-1", HVACMode.DRY)

    controller.set_state.assert_not_awaited()


def test_the_zero_valued_member_that_caused_this_is_still_zero() -> None:
    """If AUTO stops being 0 the bug is gone, and so is the reason for these tests."""
    assert pyadc.thermostat.ThermostatFanMode.AUTO == 0
    assert not pyadc.thermostat.ThermostatFanMode.AUTO


async def test_fan_on_uses_shortest_supported_positive_duration(controller):
    """A thermostat without indefinite operation must receive a supported timer."""
    controller.get.return_value.supported_fan_durations = [180, 60, 1440]
    await set_fan_mode_fn(controller, "thermostat-1", FAN_ON)
    controller.set_state.assert_awaited_once_with(
        "thermostat-1", fan_mode=pyadc.thermostat.ThermostatFanMode.ON, fan_mode_duration=60,
    )
