"""Controller interfaces with the Alarm.com API via pyalarmdotcomajax."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from types import MappingProxyType
from typing import Any

import aiohttp
import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from pyalarmdotcomajax import AlarmController as libController
from pyalarmdotcomajax import AuthResult as libAuthResult
from pyalarmdotcomajax.devices import BaseDevice as libBaseDevice
from pyalarmdotcomajax.errors import AuthenticationFailed
from pyalarmdotcomajax.errors import DataFetchFailed
from pyalarmdotcomajax.errors import UnexpectedDataStructure

from . import const as adci
from .errors import PartialInitialization

log = logging.getLogger(__name__)


class BasicAlarmHub:
    """Manages a single Alarm.com instance."""

    system: libController

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the system."""
        self.hass: HomeAssistant = hass

    @property
    def provider_name(self) -> str | None:
        """Return name of Alarm.com provider."""
        return result if (result := self.system.provider_name) else None

    @property
    def user_email(self) -> str | None:
        """Return email address for logged-in user."""
        return result if (result := self.system.user_email) else None

    @property
    def two_factor_cookie(self) -> str | None:
        """Return email address for logged-in user."""
        return result if (result := self.system.two_factor_cookie) else None

    async def async_login(
        self,
        username: str,
        password: str,
        twofactorcookie: str,
        new_websession: bool = False,
    ) -> libAuthResult:
        """Log into Alarm.com."""

        try:
            self.system = libController(
                username=username,
                password=password,
                websession=async_create_clientsession(self.hass)
                if new_websession
                else async_get_clientsession(self.hass),
                twofactorcookie=twofactorcookie,
            )

            async with async_timeout.timeout(60):

                login_result = await self.system.async_login()

                return login_result

        except UnexpectedDataStructure as err:
            raise UpdateFailed(
                "Alarm.com returned data in an unexpected format."
            ) from err
        except AuthenticationFailed as err:
            raise ConfigEntryAuthFailed("Invalid account credentials.") from err
        except (
            asyncio.TimeoutError,
            aiohttp.ClientError,
            asyncio.exceptions.CancelledError,
            ConnectionError,
        ) as err:
            log.error(
                "%s: Error logging in: %s",
                __name__,
                err,
            )
            raise err

    async def async_send_otp(self, code: int) -> None:
        """Submit two-factor authentication code and return two factor authentication cookie."""

        try:
            await self.system.async_submit_otp(
                str(code), f"Home Assistant ({self.hass.config.location_name})"
            )
        except (DataFetchFailed, AuthenticationFailed):
            log.error("OTP submission failed.")
            raise


class AlarmHub(BasicAlarmHub):
    """Config-entry initiated Alarm Hub."""

    coordinator: DataUpdateCoordinator

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        super().__init__(hass)

        self.hass: HomeAssistant = hass
        self.config_entry: ConfigEntry = config_entry
        self.options: MappingProxyType[str, Any] = config_entry.options

    @property
    def devices(self) -> list[libBaseDevice]:
        """Return dictionary of sensors for this alarmhub."""

        return list(
            self.system.sensors
            + self.system.partitions
            + self.system.cameras
            + self.system.lights
            + self.system.locks
            + self.system.garage_doors
            + self.system.systems
            + self.system.thermostats
        )

    @property
    def user_id(self) -> str | None:
        """Return Alarm.com ID for logged-in user."""
        return result if (result := self.system.user_id) else None

    async def async_setup(self, reload: bool = False) -> None:
        """Set up Alarm.com system instance."""

        if not self.config_entry:
            raise PartialInitialization

        try:
            await self.async_login(
                username=self.config_entry.data[adci.CONF_USERNAME],
                password=self.config_entry.data[adci.CONF_PASSWORD],
                twofactorcookie=self.config_entry.data.get(adci.CONF_2FA_COOKIE),
            )
        except (
            asyncio.TimeoutError,
            aiohttp.ClientError,
            asyncio.exceptions.CancelledError,
            ConnectionError,
        ) as err:
            raise ConfigEntryNotReady from err
        except (ConfigEntryAuthFailed, ConfigEntryNotReady) as err:
            raise err

        if not reload:
            log.debug("%s: Registered update listener.", __name__)
            self.config_entry.async_on_unload(
                self.config_entry.add_update_listener(_async_update_listener)
            )

        # Coordinator manages updates for all Alarmdotcom components
        self.coordinator = DataUpdateCoordinator(
            self.hass,
            log,
            name=self.config_entry.title,
            update_method=self.async_update,
            update_interval=timedelta(
                seconds=self.config_entry.options.get(
                    adci.CONF_UPDATE_INTERVAL, adci.CONF_UPDATE_INTERVAL_DEFAULT
                )
            ),
        )

        # Fetch initial data so we have data when entities subscribe.
        # Will throw exception and try again later on failure.
        await self.coordinator.async_config_entry_first_refresh()

        return None

    async def async_coordinator_update(self, critical: bool = True) -> None:
        """Force coordinator refresh. Used to force refresh after alarm control panel command."""

        if critical:
            await self.coordinator.async_refresh()
        else:
            await self.coordinator.async_request_refresh()

    async def async_update(self) -> None:
        """Pull fresh data from Alarm.com for coordinator."""

        log.debug("%s: Requesting update from Alarm.com.", __name__)

        if not self.config_entry:
            raise PartialInitialization

        try:
            await self.system.async_update()

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
                "Two-factor authentication must be enabled in order to log in with this"
                " provider."
            ) from err

        except PermissionError as err:
            raise ConfigEntryAuthFailed(
                "Account has insufficient permissions."
            ) from err

        # Typically captured during login. Should only be captured here when
        # updating after migration from configuration.yaml.
        except AuthenticationFailed as err:
            raise ConfigEntryAuthFailed("Invalid account credentials.") from err

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            log.error(
                "%s: Update failed: %s",
                __name__,
                err,
            )
            # Handled by Home Assistant Update Coordinator
            raise


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Refresh config entry when users updates configuration options."""
    await hass.config_entries.async_reload(entry.entry_id)
