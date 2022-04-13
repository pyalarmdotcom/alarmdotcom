"""Alarmdotcom implementation of an HA light."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import core
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType

from . import ADCIEntity
from . import const as adci
from .controller import ADCIController

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the button platform."""

    controller: ADCIController = hass.data[adci.DOMAIN][config_entry.entry_id]

    async_add_entities(
        ADCIDebugButton(controller, controller.devices.get("entity_data", {}).get(button_id))  # type: ignore
        for button_id in controller.devices.get("debug_ids", [])
    )


class ADCIDebugButton(ADCIEntity, ButtonEntity):  # type: ignore
    """Integration Light Entity."""

    _attr_icon = "mdi:bug"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, controller: ADCIController, device_data: adci.ADCIDebugButtonData
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(controller, device_data)

        self._device: adci.ADCIDebugButtonData = device_data
        self._config_entry: ConfigEntry = controller.config_entry

        log.debug(
            "%s: Initializing Alarm.com debug entity for %s.",
            __name__,
            self.unique_id,
        )

    @property
    def device_info(self) -> dict[str, Any]:
        """Return info to categorize this entity as a device."""

        # Associate with parent device.
        return {
            "identifiers": {(adci.DOMAIN, self._device.get("parent_id"))},
        }

    async def async_press(self) -> None:
        """Handle the button press."""

        self._controller.hass.bus.async_fire(
            adci.DEBUG_REQ_EVENT, {"device_id": self._device.get("parent_id")}
        )
