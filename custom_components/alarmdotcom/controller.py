"""Controller interfaces with the Alarm.com API via pyalarmdotcomajax."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyalarmdotcomajax import AlarmController as libAlarmController
from pyalarmdotcomajax.exceptions import (
    AlarmdotcomException,
    AuthenticationFailed,
    NotAuthorized,
    UnexpectedResponse,
)

from .const import (
    CONF_2FA_COOKIE,
    CONF_DEFAULT_UPDATE_INTERVAL_SECONDS,
    CONF_UPDATE_INTERVAL,
    KEEP_ALIVE_INTERVAL_SECONDS,
)

LOGGER = logging.getLogger(__name__)

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

        self._stop_keep_alive: CALLBACK_TYPE

        LOGGER.debug("%s: Registering update listener.", __name__)

    async def initialize(self) -> None:
        """Initialize connection to Alarm.com."""

        #
        # Create pyalarmdotcomajax controller
        #

        await self.initialize_lite(
            username=self.config_entry.data[CONF_USERNAME],
            password=self.config_entry.data[CONF_PASSWORD],
            twofactorcookie=self.config_entry.data.get(CONF_2FA_COOKIE),
        )

        #
        # Initialize DataUpdateCoordinator and pull device data
        #

        self.options = self.config_entry.options
        self.config_entry.async_on_unload(self.config_entry.add_update_listener(_async_update_listener))

        update_interval = self.config_entry.options.get(CONF_UPDATE_INTERVAL, CONF_DEFAULT_UPDATE_INTERVAL_SECONDS)

        self.update_coordinator = DataUpdateCoordinator(
            self.hass,
            LOGGER,
            name=self.config_entry.title,
            update_method=self.async_update,
            update_interval=timedelta(seconds=update_interval),
        )

        await self.update_coordinator.async_config_entry_first_refresh()

        #
        # Start keep-alive task
        #

        try:
            # Home Assistant vers >=2023.4
            self._stop_keep_alive = async_track_time_interval(
                hass=self.hass,
                action=self._keep_alive,
                interval=timedelta(seconds=KEEP_ALIVE_INTERVAL_SECONDS),
                name="Alarm.com Session Keep Alive",
            )
        except TypeError:
            # Home Assistant vers <2023.4
            self._stop_keep_alive = async_track_time_interval(
                hass=self.hass,
                action=self._keep_alive,
                interval=timedelta(seconds=KEEP_ALIVE_INTERVAL_SECONDS),
            )

    async def stop(self) -> None:
        """Stop the controller."""

        self.stop_keep_alive()
        self.api.stop_websocket()

        await self.api.close_websession()

    def stop_keep_alive(self) -> None:
        """Stop keep-alive task."""

        LOGGER.info("Stopping session keep-alive task.")

        with contextlib.suppress(TypeError):
            self._stop_keep_alive()

    async def initialize_lite(self, username: str, password: str, twofactorcookie: str | None) -> None:
        """Initialize connection to Alarm.com for config entry flow."""

        self.api = libAlarmController(
            username=username,
            password=password,
            twofactorcookie=twofactorcookie,
            websession=async_create_clientsession(self.hass),
        )

        try:
            await self.api.async_login()
        except (
            asyncio.TimeoutError,
            aiohttp.ClientError,
            asyncio.exceptions.CancelledError,
        ) as err:
            raise ConfigEntryNotReady from err
        except UnexpectedResponse as err:
            raise UpdateFailed from err
        except (AuthenticationFailed, NotAuthorized) as err:
            raise ConfigEntryAuthFailed from err

    async def _keep_alive(self, now: datetime) -> None:
        """Pass through to pyalarmdotcomajax keep_alive().

        This will be called by async_track_time_interval, which submits a datetime parameter.
        Using now as a dummy to prevent errors.
        """

        return await self.api.keep_alive()  # type: ignore

    async def async_update(self) -> None:
        """Pull fresh data from Alarm.com for coordinator."""

        LOGGER.debug("%s: Requesting update from Alarm.com.", __name__)

        try:
            await self.api.async_update()

        except NotAuthorized as err:
            raise ConfigEntryAuthFailed("Account has insufficient permissions.") from err

        # Typically captured during login. Should only be captured here when
        # updating after migration from configuration.yaml.
        except AuthenticationFailed as err:
            raise ConfigEntryAuthFailed("Invalid account credentials found while updating device states.") from err

        except AlarmdotcomException as err:
            raise UpdateFailed(str(err)) from err

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
