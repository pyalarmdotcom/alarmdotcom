"""Alarm.com controllers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from _pyalarmdotcomajax.controllers.base import BaseController
from _pyalarmdotcomajax.models.jsonapi import (
    Resource,
    SuccessDocument,
)

AdcControllerT = TypeVar("AdcControllerT", bound=BaseController)


#
# JSON:API RESPONSE CLASSES
#
@dataclass
class AdcSuccessDocumentSingle(SuccessDocument):
    """Represent a successful response with a single primary resource object."""

    data: Resource
    included: list[Resource] = field(default_factory=list)


@dataclass
class AdcSuccessDocumentMulti(SuccessDocument):
    """Represent a successful response with multiple primary resource objects."""

    data: list[Resource]
    included: list[Resource] = field(default_factory=list)


#
# /JSON:API RESPONSE CLASSES
#
