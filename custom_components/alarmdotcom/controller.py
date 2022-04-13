"""Controller interfaces with the Alarm.com API via pyalarmdotcomajax."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import aiohttp
import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from pyalarmdotcomajax import ADCController
from pyalarmdotcomajax.const import AuthResult
from pyalarmdotcomajax.errors import AuthenticationFailed
from pyalarmdotcomajax.errors import DataFetchFailed
from pyalarmdotcomajax.errors import UnexpectedDataStructure

from . import const as adci
from .errors import PartialInitialization

log = logging.getLogger(__name__)


# TODO: Commands and statuses here and in each platform file are too tightly coupled to pyalarmdotcomajax constants. Should have own constants instead.


class ADCIController:
    """Manages a single Alarm.com instance."""

    _coordinator: DataUpdateCoordinator
    _alarm: ADCController

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry | None = None
    ) -> None:
        """Initialize the system."""
        self.hass: HomeAssistant = hass
        self.config_entry: ConfigEntry = config_entry

    @property
    def devices(self) -> adci.ADCIEntities:
        """Return dictionary of sensors for this controller."""

        return self._coordinator.data  # type: ignore

    @property
    def provider_name(self) -> str | None:
        """Return name of Alarm.com provider."""
        return result if (result := self._alarm.provider_name) else None

    @property
    def user_id(self) -> str | None:
        """Return Alarm.com ID for logged-in user."""
        return result if (result := self._alarm.user_id) else None

    @property
    def user_email(self) -> str | None:
        """Return email address for logged-in user."""
        return result if (result := self._alarm.user_email) else None

    @property
    def two_factor_cookie(self) -> str | None:
        """Return email address for logged-in user."""
        return result if (result := self._alarm.two_factor_cookie) else None

    async def async_login(
        self,
        username: str,
        password: str,
        twofactorcookie: str,
    ) -> AuthResult:
        """Log into Alarm.com."""

        try:
            self._alarm = ADCController(
                username=username,
                password=password,
                websession=async_get_clientsession(self.hass),
                twofactorcookie=twofactorcookie,
            )

            async with async_timeout.timeout(45):
                login_result = await self._alarm.async_login()

                return login_result

        except ConnectionError as err:
            raise UpdateFailed("Error communicating with alarm.com") from err
        except AuthenticationFailed as err:
            raise ConfigEntryAuthFailed("Invalid account credentials.") from err
        except (asyncio.TimeoutError, aiohttp.ClientError):
            # Handled by Home Assistant Update Coordinator.
            raise

    async def async_send_otp(self, code: int) -> None:
        """Submit two-factor authentication code and return two factor authentication cookie."""

        try:
            await self._alarm.async_submit_otp(
                str(code), f"Home Assistant ({self.hass.config.location_name})"
            )
        except (DataFetchFailed, AuthenticationFailed):
            log.error("OTP submission failed.")
            raise

    async def async_setup(self, reload: bool = False) -> bool:
        """Set up Alarm.com system instance."""
        log.debug(
            "%s: Setting up controller with config_entry: %s",
            __name__,
            self.config_entry.data,
        )

        if not self.config_entry:
            raise PartialInitialization

        await self.async_login(
            username=self.config_entry.data[adci.CONF_USERNAME],
            password=self.config_entry.data[adci.CONF_PASSWORD],
            twofactorcookie=self.config_entry.data.get(adci.CONF_2FA_COOKIE),
        )

        if not reload:
            log.debug("%s: Registered update listener.", __name__)
            self.config_entry.async_on_unload(
                self.config_entry.add_update_listener(_async_update_listener)
            )

        # This is indicitive of a problem. Just flag for now.
        if self.config_entry.title is None:
            log.error("Config entry has no title.")

        # Coordinator manages updates for all Alarmdotcom components
        self._coordinator = DataUpdateCoordinator(
            self.hass,
            log,
            name=self.config_entry.title,
            # name="alarmdotcom",
            update_method=self.async_update,
            update_interval=timedelta(
                seconds=self.config_entry.options.get(
                    adci.CONF_UPDATE_INTERVAL, adci.CONF_UPDATE_INTERVAL_DEFAULT
                )
            ),
        )

        # Fetch initial data so we have data when entities subscribe.
        # Will throw exception and try again later on failure.
        await self._coordinator.async_config_entry_first_refresh()

        return True

    async def async_coordinator_update(self, critical: bool = True) -> None:
        """Force coordinator refresh. Used to force refresh after alarm control panel command."""

        if critical:
            await self._coordinator.async_refresh()
        else:
            await self._coordinator.async_request_refresh()

    async def async_update(self) -> adci.ADCIEntities:
        """Pull fresh data from Alarm.com for coordinator."""

        if not self.config_entry:
            raise PartialInitialization

        try:
            await self._alarm.async_update()

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

        except (asyncio.TimeoutError, aiohttp.ClientError):
            # Handled by Home Assistant Update Coordinator
            raise

        entity_data: dict = {}
        system_ids: set[str] = set()
        partition_ids: set[str] = set()
        sensor_ids: set[str] = set()
        lock_ids: set[str] = set()
        light_ids: set[str] = set()
        garage_door_ids: set[str] = set()
        low_battery_ids: set[str] = set()
        malfunction_ids: set[str] = set()
        debug_ids: set[str] = set()

        log.debug("Processing systems.")

        # Process systems
        for src_sys in self._alarm.systems:

            log.debug("%s: %s", src_sys.id_, src_sys.name)

            dest_sys: adci.ADCISystemData = {
                "unique_id": src_sys.id_,
                "name": src_sys.name,
                "malfunction": src_sys.malfunction,
                "unit_id": src_sys.unit_id,
                "mac_address": src_sys.mac_address,
                "debug_data": src_sys.debug_data,
            }

            entity_data[src_sys.id_] = dest_sys
            system_ids.add(src_sys.id_)

        log.debug("Processing partitions.")

        # Process partitions
        for src_part in self._alarm.partitions:

            log.debug("%s: %s", src_part.id_, src_part.name)

            dest_part: adci.ADCIPartitionData = {
                "unique_id": src_part.id_,
                "name": src_part.name,
                "state": src_part.state,
                "malfunction": src_part.malfunction,
                "parent_id": src_part.system_id,
                "mac_address": src_part.mac_address,
                "raw_state_text": src_part.raw_state_text,
                "desired_state": src_part.desired_state,
                "uncleared_issues": src_part.uncleared_issues,
                "async_arm_away_callback": src_part.async_arm_away,
                "async_arm_home_callback": src_part.async_arm_stay,
                "async_disarm_callback": src_part.async_disarm,
                "async_arm_night_callback": src_part.async_arm_night,
                "read_only": src_part.read_only,
                "debug_data": src_part.debug_data,
            }

            entity_data[src_part.id_] = dest_part
            partition_ids.add(src_part.id_)

        log.debug("Processing sensors.")

        # Process sensors
        for src_sensor in self._alarm.sensors:

            log.debug("%s: %s", src_sensor.id_, src_sensor.name)

            if src_sensor.device_subtype in adci.SENSOR_SUBTYPE_BLACKLIST:
                log.debug(
                    "Skipping blacklisted sensor %s (%s)",
                    src_sensor.name,
                    src_sensor.id_,
                )
                continue

            dest_sensor: adci.ADCISensorData = {
                "unique_id": src_sensor.id_,
                "name": src_sensor.name,
                "state": src_sensor.state,
                "malfunction": src_sensor.malfunction,
                "parent_id": src_sensor.partition_id,
                "battery_low": src_sensor.battery_low or src_sensor.battery_critical,
                "mac_address": src_sensor.mac_address,
                "raw_state_text": src_sensor.raw_state_text,
                "device_subtype": src_sensor.device_subtype,
                "debug_data": src_sensor.debug_data,
            }

            entity_data[src_sensor.id_] = dest_sensor
            sensor_ids.add(src_sensor.id_)

        log.debug("Processing locks.")

        # Process locks
        for src_lock in self._alarm.locks:

            log.debug("%s: %s", src_lock.id_, src_lock.name)

            dest_lock: adci.ADCILockData = {
                "unique_id": src_lock.id_,
                "name": src_lock.name,
                "state": src_lock.state,
                "malfunction": src_lock.malfunction,
                "parent_id": src_lock.partition_id,
                "battery_low": src_lock.battery_low or src_lock.battery_critical,
                "mac_address": src_lock.mac_address,
                "raw_state_text": src_lock.raw_state_text,
                "desired_state": src_lock.desired_state,
                "async_lock_callback": src_lock.async_lock,
                "async_unlock_callback": src_lock.async_unlock,
                "read_only": src_lock.read_only,
                "debug_data": src_lock.debug_data,
            }

            entity_data[src_lock.id_] = dest_lock
            lock_ids.add(src_lock.id_)

        log.debug("Processing lights.")

        # Process lights
        for src_light in self._alarm.lights:

            log.debug("%s: %s", src_light.id_, src_light.name)

            dest_light: adci.ADCILightData = {
                "unique_id": src_light.id_,
                "name": src_light.name,
                "state": src_light.state,
                "malfunction": src_light.malfunction,
                "parent_id": src_light.partition_id,
                "mac_address": src_light.mac_address,
                "raw_state_text": src_light.raw_state_text,
                "desired_state": src_light.desired_state,
                "brightness": src_light.brightness,
                "async_turn_on_callback": src_light.async_turn_on,
                "async_turn_off_callback": src_light.async_turn_off,
                "read_only": src_light.read_only,
                "supports_state_tracking": src_light.supports_state_tracking,
                "debug_data": src_light.debug_data,
            }

            entity_data[src_light.id_] = dest_light
            light_ids.add(src_light.id_)

        log.debug("Processing garage doors.")

        # Process garage doors
        for src_garage in self._alarm.garage_doors:

            log.debug("%s: %s", src_garage.id_, src_garage.name)

            dest_garage: adci.ADCIGarageDoorData = {
                "unique_id": src_garage.id_,
                "name": src_garage.name,
                "state": src_garage.state,
                "malfunction": src_garage.malfunction,
                "parent_id": src_garage.partition_id,
                "mac_address": src_garage.mac_address,
                "raw_state_text": src_garage.raw_state_text,
                "desired_state": src_garage.desired_state,
                "async_close_callback": src_garage.async_close,
                "async_open_callback": src_garage.async_open,
                "read_only": src_garage.read_only,
                "debug_data": src_garage.debug_data,
            }

            entity_data[src_garage.id_] = dest_garage
            garage_door_ids.add(src_garage.id_)

        log.debug("Processing low battery sensors.")

        # Process "virtual" battery sensors for sensors and locks.
        for parent_id in sensor_ids.union(lock_ids):

            battery_parent: adci.ADCISensorData | adci.ADCILockData = entity_data[
                parent_id
            ]

            dest_batt: adci.ADCISensorData = {
                "unique_id": f"{battery_parent.get('unique_id')}_low_battery",
                "name": f"{battery_parent.get('name')}: Battery",
                "state": battery_parent.get("battery_low"),
                "parent_id": battery_parent["unique_id"],
            }

            log.debug("%s: %s", dest_batt.get("unique_id"), dest_batt.get("name"))

            entity_data[dest_batt["unique_id"]] = dest_batt
            low_battery_ids.add(dest_batt["unique_id"])

        log.debug("Processing malfunction sensors.")

        # Process "virtual" malfunction sensors for sensors, locks, lights, and partitions.
        for parent_id in sensor_ids.union(lock_ids, partition_ids):

            # TODO: Add garage door malfunction sensors.

            malfunction_parent: adci.ADCISensorData | adci.ADCILockData | adci.ADCILightData | adci.ADCIPartitionData = entity_data[
                parent_id
            ]

            dest_malfunction: adci.ADCISensorData = {
                "unique_id": f"{malfunction_parent.get('unique_id')}_malfunction",
                "name": f"{malfunction_parent.get('name')}: Malfunction",
                "parent_id": malfunction_parent["unique_id"],
                "state": malfunction_parent.get("malfunction"),
            }

            log.debug(
                "%s: %s",
                dest_malfunction.get("unique_id"),
                dest_malfunction.get("name"),
            )

            entity_data[dest_malfunction["unique_id"]] = dest_malfunction
            malfunction_ids.add(dest_malfunction["unique_id"])

        # Process debug buttons for all entities.
        for parent_id in sensor_ids.union(
            lock_ids, partition_ids, light_ids, garage_door_ids, system_ids
        ):

            debug_parent: adci.ADCISensorData | adci.ADCILockData | adci.ADCILightData | adci.ADCIPartitionData | adci.ADCIGarageDoorData | adci.ADCISystemData = entity_data[
                parent_id
            ]

            dest_debug: adci.ADCIDebugButtonData = {
                "unique_id": f"{debug_parent.get('unique_id')}_debug",
                "name": f"{debug_parent.get('name')}: Debug",
                "parent_id": debug_parent["unique_id"],
            }

            log.debug(
                "%s: %s",
                debug_parent.get("unique_id"),
                debug_parent.get("name"),
            )

            entity_data[dest_debug["unique_id"]] = dest_debug
            debug_ids.add(dest_debug["unique_id"])

        # Load objects to devices dict:

        devices: adci.ADCIEntities = {
            "entity_data": entity_data,
            "system_ids": system_ids,
            "partition_ids": partition_ids,
            "sensor_ids": sensor_ids,
            "lock_ids": lock_ids,
            "light_ids": light_ids,
            "garage_door_ids": garage_door_ids,
            "low_battery_ids": low_battery_ids,
            "malfunction_ids": malfunction_ids,
            "debug_ids": debug_ids,
        }

        return devices


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Refresh config entry when users updates configuration options."""
    await hass.config_entries.async_reload(entry.entry_id)
