"""Alarm.com controller for trouble conditions."""

from _pyalarmdotcomajax.controllers.base import BaseController
from _pyalarmdotcomajax.models.base import ResourceType
from _pyalarmdotcomajax.models.trouble_condition import TroubleCondition

from .base import device_controller


@device_controller(ResourceType.TROUBLE_CONDITION, TroubleCondition)
class TroubleConditionController(BaseController[TroubleCondition]):
    """Controller for trouble conditions."""

    # Trouble records describe the current conditions, rather than permanent devices.
    # IDs can change between successful responses. Keeping an absent record for three
    # polls leaves cleared conditions active and counts replacements more than once.
    # Failed requests never reach reconciliation, so they still preserve known state.
    _missing_refreshes_before_removal = 1
