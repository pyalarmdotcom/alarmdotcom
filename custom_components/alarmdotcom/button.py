"""Alarmdotcom implementation of an HA button."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant import core
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback, DiscoveryInfoType
from pyalarmdotcomajax.devices.registry import AllDevices_t

from .base_device import AttributeBaseDevice
from .const import DATA_CONTROLLER, DEBUG_REQ_EVENT, DOMAIN, SENSOR_SUBTYPE_BLACKLIST
from .controller import AlarmIntegrationController

LOGGER = logging.getLogger(__name__)


@dataclass
class AlarmdotcomButtonDescriptionMixin:
    """Functions for an attribute entity."""

    filter_fn: Callable[[AllDevices_t], bool]
    press_fn: Callable[[HomeAssistant, AllDevices_t], Any]


@dataclass
class AlarmdotcomButtonDescription(ButtonEntityDescription, AlarmdotcomButtonDescriptionMixin):  # type: ignore
    """Describes a button entity."""


ATTRIBUTE_BUTTONS: Final = [
    AlarmdotcomButtonDescription(
        key="debug",
        name="Debug",
        has_entity_name=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda hass, device: hass.bus.async_fire(DEBUG_REQ_EVENT, {"device_id": device.id_}),
        filter_fn=lambda device: device.has_state is True
        and (getattr(device, "device_subtype") not in SENSOR_SUBTYPE_BLACKLIST),
        icon="mdi:bug",
    ),
]


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the button platform."""

    controller: AlarmIntegrationController = hass.data[DOMAIN][config_entry.entry_id][DATA_CONTROLLER]

    async_add_entities(
        DebugButton(controller=controller, device=device, description=description)
        for description in ATTRIBUTE_BUTTONS
        for device in controller.api.devices.all.values()
        if description.filter_fn(device)
    )


class DebugButton(AttributeBaseDevice, ButtonEntity):  # type: ignore
    """Integration button entity."""

    entity_description: AlarmdotcomButtonDescription
    _attr_available: bool = True

    async def async_press(self) -> None:
        """Handle the button press."""

        self.entity_description.press_fn(self.hass, self._device)
