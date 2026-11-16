"""Alarm.com models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from _pyalarmdotcomajax.models.base import (
    AdcDeviceResource,
    AdcResource,
    BaseManagedDeviceAttributes,
)
from _pyalarmdotcomajax.models.jsonapi import Error, JsonApiBaseElement
from mashumaro import field_options

AdcResourceT = TypeVar("AdcResourceT", bound=AdcResource)
AdcManagedDeviceT = TypeVar(
    "AdcManagedDeviceT", bound=AdcDeviceResource[BaseManagedDeviceAttributes]
)


@dataclass
class AdcMiniSuccessResponse(JsonApiBaseElement):
    """
    Represents a success response object from Alarm.com "mini" endpoints.

    Includes:
    - WebSocket token
    - OTP Submission

    This response is not JSON:API compliant.

    Class will fail validation by AlarmBridge.request() if errors are present; response will then be processed as FailureDocument.

    This is likely a modified hapi/boom response object: https://hapi.dev/module/boom/api/?v=10.0.1
    """

    # fmt: off
    value: str | None = field(default=None)
    errors: list[Error] = field(default_factory=list)
    metadata: dict = field(default_factory=dict, metadata=field_options(alias="meta_data"))
    # fmt: on

    @classmethod
    def __post_deserialize__(
        cls, obj: AdcMiniSuccessResponse
    ) -> AdcMiniSuccessResponse:
        """Validate values after deserialization."""

        if obj.errors:
            raise ValueError("Response has errors")

        return obj
