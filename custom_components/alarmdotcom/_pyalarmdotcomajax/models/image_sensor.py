"""Alarm.com model for image sensors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from _pyalarmdotcomajax.models.base import (
    AdcDeviceResource,
    AdcResourceAttributes,
    ResourceType,
)
from _pyalarmdotcomajax.util import get_related_entity_id_by_key


@dataclass
class ImageSensorAttributes(AdcResourceAttributes):
    """
    Attributes of an image sensor.

    Image sensors don't have states.
    """

    # fmt: off
    is_image_sensor_deleted: bool = field(metadata={"description": "Indicates whether the device has been deleted."}, default=False)
    support_peek_in_now: bool = field(metadata={"description": "Indicates whether the device supports PeekInNow feature."}, default=False)
    can_view_images: bool = field(metadata={"description": "Specifies whether the currently logged in user can view images for this sensor."}, default=False)
    support_peek_in_next_motion: bool = field(metadata={"description": "Indicates whether the device supports PeekInNextMotion feature."}, default=False)
    # fmt: on


@dataclass
class ImageSensor(AdcDeviceResource[ImageSensorAttributes]):
    """Image sensor resource."""

    resource_type = ResourceType.IMAGE_SENSOR
    attributes_type = ImageSensorAttributes

    latest_image: ImageSensorImage | None = field(init=False, default=None)

    async def _on_new_image(self, images: list[ImageSensorImage]) -> None:
        """Handle new image event."""

        if not images:
            return

        # Get the latest image by checking for the most recent time stamp for an image associated with this image sensor.
        # Filter images to only those associated with this image sensor's id
        filtered_images = [image for image in images if image.image_sensor_id == self.id]
        if not filtered_images:
            return

        latest_image = max(filtered_images, key=lambda image: image.attributes.timestamp)

        # Check if the latest image is different from the current one
        if self.latest_image and self.latest_image.id == latest_image.id:
            return

        self.latest_image = latest_image


@dataclass
class ImageSensorImageAttributes(AdcResourceAttributes):
    """Image sensor image attributes."""

    image: str = field(metadata={"description": "The Base64 encoded image."})
    image_src: str = field(metadata={"description": "URI for the image sensor image source."})
    timestamp: str = field(metadata={"description": "Time stamp of when the image was taken."})


@dataclass
class ImageSensorImage(AdcDeviceResource[ImageSensorImageAttributes]):
    """Image sensor image resource."""

    resource_type = ResourceType.IMAGE_SENSOR_IMAGE
    attributes_type = ImageSensorImageAttributes
    has_related_system: ClassVar[bool] = False

    @property
    def image_sensor_id(self) -> str | None:
        """Image sensor ID."""

        return get_related_entity_id_by_key(self.api_resource, "image_sensor")
