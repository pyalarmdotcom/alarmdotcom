"""The alarmdotcom integration."""

from __future__ import annotations

import logging
import async_timeout

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, STARTUP_MESSAGE
from .util import map_adc_provider

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["alarm_control_panel"]


async def async_setup(hass: HomeAssistantType, config: dict):
    """Create alarmdotcom domain entry."""

    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up alarmdotcom controller from a config entry."""

    if DOMAIN not in hass.data:
        # Print startup message
        _LOGGER.info(STARTUP_MESSAGE)

    adc_class = map_adc_provider(entry.data["provider"])

    api = adc_class(
        username=entry.data["username"],
        password=entry.data["password"],
        websession=async_get_clientsession(hass),
        forcebypass=False,
        noentrydelay=False,
        silentarming=False,
        twofactorcookie=entry.data["two_factor"],
    )

    login_response = await api.async_login()
    if not login_response:
        raise ConfigEntryAuthFailed

    async def async_update_data():
        # ADC library should throw exception when connection fails instead of returning True/False.
        async with async_timeout.timeout(10):
            update_response = await api.async_update()
            if not update_response:
                raise UpdateFailed("Error communicating with API.")
            return api.state

    # Coordinator communicates with API on behalf of all ADC entities.
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(minutes=1),
    )

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
