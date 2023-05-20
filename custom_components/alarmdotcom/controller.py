"""Controller interfaces with the Alarm.com API via pyalarmdotcomajax."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from types import MappingProxyType
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyalarmdotcomajax import AlarmController as libAlarmController
from pyalarmdotcomajax.errors import (
    AuthenticationFailed,
    UnexpectedDataStructure,
)

from .const import CONF_2FA_COOKIE, CONF_UPDATE_INTERVAL_DEFAULT

log = logging.getLogger(__name__)

# TODO: Move websocket control here and include handler to restart if connection is lost.


class AlarmIntegrationController:
    """Config-entry initiated Alarm Hub."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""

        self.hass: HomeAssistant = hass
        self.config_entry: ConfigEntry = config_entry

        self.update_coordinator: DataUpdateCoordinator
        self.api: libAlarmController

        self.options: MappingProxyType[str, Any]

        log.debug("%s: Registering update listener.", __name__)

    async def initialize(self) -> None:
        """Initialize connection to Alarm.com."""

        self.api = libAlarmController(
            username=self.config_entry.data[CONF_USERNAME],
            password=self.config_entry.data[CONF_PASSWORD],
            twofactorcookie=self.config_entry.data.get(CONF_2FA_COOKIE),
            websession=async_get_clientsession(self.hass),
        )

        await self._login()

        self.options = self.config_entry.options
        self.config_entry.async_on_unload(self.config_entry.add_update_listener(_async_update_listener))

        self.update_coordinator = DataUpdateCoordinator(
            self.hass,
            log,
            name=self.config_entry.title,
            update_method=self.async_update,
            update_interval=timedelta(seconds=CONF_UPDATE_INTERVAL_DEFAULT),
        )

        await self.update_coordinator.async_config_entry_first_refresh()

    async def initialize_lite(self, username: str, password: str, twofactorcookie: str | None) -> None:
        """Initialize connection to Alarm.com for config entry flow."""

        self.api = libAlarmController(
            username=username,
            password=password,
            twofactorcookie=twofactorcookie,
            websession=async_get_clientsession(self.hass),
        )

        return await self._login()

    async def _login(self) -> None:
        """Login to Alarm.com."""

        try:
            await self.api.async_login()
        except (
            asyncio.TimeoutError,
            aiohttp.ClientError,
            asyncio.exceptions.CancelledError,
            ConnectionError,
        ) as err:
            raise ConfigEntryNotReady from err
        except UnexpectedDataStructure as err:
            raise UpdateFailed("Alarm.com returned data in an unexpected format.") from err
        except AuthenticationFailed as err:
            raise ConfigEntryAuthFailed("Invalid account credentials found while logging in.") from err

    async def async_update(self) -> None:
        """Pull fresh data from Alarm.com for coordinator."""

        log.debug("%s: Requesting update from Alarm.com.", __name__)

        try:
            await self.api.async_update()

        except (UnexpectedDataStructure, ConnectionError) as err:
            log.error(
                "%s: Update failed: %s",
                __name__,
                err,
            )
            raise UpdateFailed("Error communicating with api.") from err

        # TypeError encountered when importing from configuration.yaml using
        # a provider that requires 2FA with an account that does not
        # have 2FA set up.
        except TypeError as err:
            raise ConfigEntryAuthFailed(
                "async_update(): Two-factor authentication must be enabled in order to log in with this provider."
            ) from err

        except PermissionError as err:
            raise ConfigEntryAuthFailed("Account has insufficient permissions.") from err

        # Typically captured during login. Should only be captured here when
        # updating after migration from configuration.yaml.
        except AuthenticationFailed as err:
            raise ConfigEntryAuthFailed("Invalid account credentials found while updating device states.") from err

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            log.error(
                "%s: Update failed: %s",
                __name__,
                err,
            )
            # Handled by Home Assistant Update Coordinator
            raise

    @property
    def provider_name(self) -> str:
        """Return the name of the provider."""
        return str(self.api.provider_name)

    @property
    def user_email(self) -> str:
        """Return the user email."""
        return str(self.api.user_email)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Refresh config entry when users updates configuration options."""
    await hass.config_entries.async_reload(entry.entry_id)
