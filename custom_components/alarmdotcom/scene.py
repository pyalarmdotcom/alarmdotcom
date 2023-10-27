"""Alarmdotcom implementation of an HA scene."""

from __future__ import annotations

import logging

from homeassistant import core
from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback, DiscoveryInfoType
from pyalarmdotcomajax.devices.scene import Scene as libScene

from .base_device import HardwareBaseDevice
from .const import DATA_CONTROLLER, DOMAIN
from .controller import AlarmIntegrationController

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the button platform."""

    controller: AlarmIntegrationController = hass.data[DOMAIN][config_entry.entry_id][DATA_CONTROLLER]

    async_add_entities(
        Scene(
            controller=controller,
            device=device,
        )
        for device in controller.api.devices.scenes.values()
        if device.read_only is False
    )


class Scene(HardwareBaseDevice, Scene):  # type: ignore
    """Integration button entity."""

    _device_type_name: str = "Scene"
    _device: libScene

    async def async_activate(self) -> None:
        """Handle the button press."""

        await self._device.execute()
