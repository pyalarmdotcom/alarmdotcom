"""Alarm.com controller for image sensors."""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import TYPE_CHECKING

from _pyalarmdotcomajax.adc.util import Param_Id, cli_action
from _pyalarmdotcomajax.controllers.base import BaseController, device_controller
from _pyalarmdotcomajax.models.base import ResourceType
from _pyalarmdotcomajax.models.image_sensor import ImageSensor, ImageSensorImage
from _pyalarmdotcomajax.websocket.client import SupportedResourceEvents
from _pyalarmdotcomajax.websocket.messages import (
    BaseWSMessage,
    EventWSMessage,
    ResourceEventType,
)

if TYPE_CHECKING:
    from _pyalarmdotcomajax.models import AdcResourceT

log = logging.getLogger(__name__)


class ImageSensorCommand(StrEnum):
    """Commands for ADC image sensors."""

    PEEK_IN = "doPeekInNow"


@device_controller(ResourceType.IMAGE_SENSOR, ImageSensor)
class ImageSensorController(BaseController[ImageSensor]):
    """Controller for image sensors."""

    _supported_resource_events = SupportedResourceEvents(
        events=[ResourceEventType.ImageSensorUpload]
    )

    @cli_action()
    async def peek_in(self, id: Param_Id) -> None:
        """Take a peek in photo."""

        await self._send_command(id, ImageSensorCommand.PEEK_IN)

    async def _handle_event(
        self, adc_resource: AdcResourceT, message: BaseWSMessage
    ) -> AdcResourceT:
        """
        Handle events for image sensor images.

        Updates attributes on ResourceEventType.ImageSensorUpload.
        """

        log.debug(
            "Handling event for image sensor %s: %s",
            adc_resource.id,
            message,
        )

        if (
            isinstance(message, EventWSMessage)
            and message.subtype == ResourceEventType.ImageSensorUpload
            and message.value is not None
        ):
            adc_resource.api_resource.attributes.update(
                image=message.value,
                image_src=message.subvalue,
                timestamp=message.event_date_utc.isoformat(),
            )

        return adc_resource


class ImageSensorImageController(BaseController[ImageSensorImage]):
    """Controller for image sensor images."""

    resource_type = ResourceType.IMAGE_SENSOR_IMAGE
    _resource_class = ImageSensorImage
    _resource_url_override = "imageSensor/imageSensorImages/getRecentImages"
