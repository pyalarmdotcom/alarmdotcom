"""Alarm.com model for device catalogs."""

from dataclasses import dataclass

from _pyalarmdotcomajax.models.base import (
    AdcResource,
    AdcResourceAttributes,
    ResourceType,
)


@dataclass
class DeviceCatalogAttributes(AdcResourceAttributes):
    """Attributes of alarm system."""


@dataclass
class DeviceCatalog(AdcResource[DeviceCatalogAttributes]):
    """System resource."""

    resource_type = ResourceType.DEVICE_CATALOG
    attributes_type = DeviceCatalogAttributes
