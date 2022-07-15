"""Alarmdotcom implementation of an HA button."""
from __future__ import annotations

import logging

from homeassistant import core
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from pyalarmdotcomajax.devices.sensor import Sensor as libSensor

from .alarmhub import AlarmHub
from .base_device import AttributeBaseDevice
from .base_device import AttributeSubdevice
from .const import DEBUG_REQ_EVENT
from .const import DOMAIN
from .const import SENSOR_SUBTYPE_BLACKLIST

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the button platform."""

    alarmhub: AlarmHub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        DebugAttributeDevice(
            alarmhub=alarmhub, device=device, subdevice_type=AttributeSubdevice.DEBUG
        )
        for device in alarmhub.devices
        if None not in [device.battery_low, device.battery_critical]
        and not (
            isinstance(device, libSensor)
            and device.device_subtype in SENSOR_SUBTYPE_BLACKLIST
        )
    )


class DebugAttributeDevice(AttributeBaseDevice, ButtonEntity):  # type: ignore
    """Integration button entity."""

    _attr_icon = "mdi:bug"

    async def async_press(self) -> None:
        """Handle the button press."""

        self.hass.bus.async_fire(DEBUG_REQ_EVENT, {"device_id": self._device.id_})

    @callback  # type: ignore
    def update_device_data(self) -> None:
        """Update the entity when new data comes from the REST API."""
