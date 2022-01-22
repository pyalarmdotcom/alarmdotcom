"""Controller interfaces with the Alarm.com API via pyalarmdotcomajax."""

from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pyalarmdotcomajax import ADCController
from pyalarmdotcomajax.const import (
    ADCDeviceType,
    ADCGarageDoorCommand,
    ADCLockCommand,
    ADCPartitionCommand,
)
from pyalarmdotcomajax.errors import AuthenticationFailed, UnexpectedDataStructure

from . import const as adci

log = logging.getLogger(__name__)


# TODO: Commands and statuses here and in each platform file are too tightly coupled to pyalarmdotcomajax constants. Should have own constants instead.


class ADCIController:
    """Manages a single Alarm.com instance."""

    coordinator: DataUpdateCoordinator
    api: ADCController

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize the system."""
        self.hass: HomeAssistant = hass
        self.config_entry: ConfigEntry = config_entry

    @property
    def devices(self) -> adci.ADCIEntities:
        """Return dictionary of sensors for this controller."""

        return self.coordinator.data  # type: ignore

    async def async_setup(self, reload: bool = False) -> bool:
        """Set up Alarm.com system instance."""
        log.debug(
            "%s: Setting up controller with config_entry: %s",
            __name__,
            self.config_entry.data,
        )
        try:
            self.api = await get_controller(
                self.hass,
                self.config_entry.data[adci.CONF_USERNAME],
                self.config_entry.data[adci.CONF_PASSWORD],
                self.config_entry.data[adci.CONF_2FA_COOKIE],
                self.config_entry.options.get(adci.CONF_FORCE_BYPASS),
                self.config_entry.options.get(adci.CONF_NO_DELAY),
                self.config_entry.options.get(adci.CONF_SILENT_ARM),
            )
        except ConnectionError as err:
            log.debug(
                "%s: get_controller failed with CannotConnect exception: %s",
                __name__,
                err,
            )
            raise ConfigEntryNotReady from err
        except AuthenticationFailed as err:
            log.debug(
                "%s: get_controller failed with InvalidAuth exception: %s",
                __name__,
                err,
            )
            raise ConfigEntryAuthFailed from err

        if not reload:
            log.debug("%s: Registered update listener.", __name__)
            self.config_entry.async_on_unload(
                self.config_entry.add_update_listener(self._async_update_listener)
            )

        # Coordinator manages updates for all Alarmdotcom components
        self.coordinator = DataUpdateCoordinator(
            self.hass,
            log,
            name=self.config_entry.title,
            update_method=self.async_update,
            update_interval=timedelta(minutes=1),
        )

        # Fetch initial data so we have data when entities subscribe.
        # Will throw exception and try again later on failure.
        await self.coordinator.async_config_entry_first_refresh()

        return True

    async def async_update(self) -> adci.ADCIEntities:
        """Pull fresh data from Alarm.com for coordinator."""

        try:
            await self.api.async_update()
        except (PermissionError, UnexpectedDataStructure) as err:
            raise UpdateFailed("Error communicating with API.") from err

        entity_data: dict = {}
        system_ids: set[str] = set()
        partition_ids: set[str] = set()
        sensor_ids: set[str] = set()
        lock_ids: set[str] = set()
        garage_door_ids: set[str] = set()
        low_battery_ids: set[str] = set()
        malfunction_ids: set[str] = set()

        # Process systems
        for src_sys in self.api.systems:

            dest_sys: adci.ADCISystemData = {
                "unique_id": src_sys.id_,
                "name": src_sys.name,
                "malfunction": src_sys.malfunction,
                "unit_id": src_sys.unit_id,
                "mac_address": src_sys.mac_address,
            }

            entity_data[src_sys.id_] = dest_sys
            system_ids.add(src_sys.id_)

        # Process partitions
        for src_part in self.api.partitions:

            dest_part: adci.ADCIPartitionData = {
                "unique_id": src_part.id_,
                "name": src_part.name,
                "state": src_part.state,
                "malfunction": src_part.malfunction,
                "parent_id": src_part.system_id,
                "mac_address": src_part.mac_address,
                "raw_state_text": src_part.raw_state_text,
                "mismatched_states": src_part.mismatched_states,
                "desired_state": src_part.desired_state,
                "uncleared_issues": src_part.uncleared_issues,
                "async_arm_away_callback": src_part.async_alarm_arm_away,
                "async_arm_stay_callback": src_part.async_alarm_arm_stay,
                "async_disarm_callback": src_part.async_alarm_disarm,
                "async_arm_night_callback": src_part.async_alarm_arm_night,
            }

            entity_data[src_part.id_] = dest_part
            partition_ids.add(src_part.id_)

        # Process sensors
        for src_sensor in self.api.sensors:

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
            }

            entity_data[src_sensor.id_] = dest_sensor
            sensor_ids.add(src_sensor.id_)

        # Process locks
        for src_lock in self.api.locks:

            dest_lock: adci.ADCILockData = {
                "unique_id": src_lock.id_,
                "name": src_lock.name,
                "state": src_lock.state,
                "malfunction": src_lock.malfunction,
                "parent_id": src_lock.partition_id,
                "battery_low": src_lock.battery_low or src_lock.battery_critical,
                "mac_address": src_lock.mac_address,
                "raw_state_text": src_lock.raw_state_text,
                "mismatched_states": src_lock.mismatched_states,
                "desired_state": src_lock.desired_state,
                "async_lock_callback": src_lock.async_lock,
                "async_unlock_callback": src_lock.async_unlock,
            }

            entity_data[src_lock.id_] = dest_lock
            lock_ids.add(src_lock.id_)

        # Process garage doors
        for src_garage in self.api.garage_doors:

            dest_garage: adci.ADCIGarageDoorData = {
                "unique_id": src_garage.id_,
                "name": src_garage.name,
                "state": src_garage.state,
                "malfunction": src_garage.malfunction,
                "parent_id": src_garage.partition_id,
                "mac_address": src_garage.mac_address,
                "raw_state_text": src_garage.raw_state_text,
                "mismatched_states": src_garage.mismatched_states,
                "desired_state": src_garage.desired_state,
                "async_close_callback": src_garage.async_close,
                "async_open_callback": src_garage.async_open,
            }

            entity_data[src_garage.id_] = dest_garage
            garage_door_ids.add(src_garage.id_)

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

            entity_data[dest_batt["unique_id"]] = dest_batt
            low_battery_ids.add(dest_batt["unique_id"])

        # Process "virtual" malfunction sensors for sensors, locks, and partitions.
        for parent_id in sensor_ids.union(lock_ids, partition_ids):

            malfunction_parent: adci.ADCISensorData | adci.ADCILockData | adci.ADCIPartitionData = entity_data[
                parent_id
            ]

            dest_malfunction: adci.ADCISensorData = {
                "unique_id": f"{malfunction_parent.get('unique_id')}_malfunction",
                "name": f"{malfunction_parent.get('name')}: Malfunction",
                "parent_id": malfunction_parent["unique_id"],
                "state": malfunction_parent.get("malfunction") or malfunction_parent.get("mismatched_states", False)  # type: ignore
                if "mismatched_states" in malfunction_parent
                else malfunction_parent.get("malfunction"),
            }

            # (malfunction_parent.get("malfunction") or malfunction_parent.get("mismatched_states", False)) or False

            entity_data[dest_malfunction["unique_id"]] = dest_malfunction
            malfunction_ids.add(dest_malfunction["unique_id"])

        # Load objects to devices dict:

        devices: adci.ADCIEntities = {
            "entity_data": entity_data,
            "system_ids": system_ids,
            "partition_ids": partition_ids,
            "sensor_ids": sensor_ids,
            "lock_ids": lock_ids,
            "garage_door_ids": garage_door_ids,
            "low_battery_ids": low_battery_ids,
            "malfunction_ids": malfunction_ids,
        }

        return devices

    async def _async_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        await hass.config_entries.async_reload(entry.entry_id)

    # #
    # Actions
    # #

    async def _async_send_action(
        self,
        entity_id: str,
        action: ADCPartitionCommand | ADCLockCommand | ADCGarageDoorCommand,
        device_type: ADCDeviceType,
    ) -> bool:
        """Send action request to API & handle errors."""
        try:
            response: bool = await self.api.async_send_action(
                device_type=device_type, event=action, device_id=entity_id
            )
        except PermissionError as err:
            log.error("%s: Inadequate permissions. %s", __name__, str(err))
            # TODO: This notification needs work. Actions should be user-readable. Device type should be a HA device type (alarm control panel instead of partition). Device name should be shown.
            error_msg = (
                "Your Alarm.com user does not have permission to"
                f" {action.value.lower()} your {device_type.name.lower()}. Please log"
                " in to Alarm.com to grant the appropriate permissions to your"
                " account."
            )
            persistent_notification.async_create(
                self.hass,
                error_msg,
                title="Alarm.com Error",
                notification_id="alarmcom_permission_error",
            )
            return False

        await self.coordinator.async_refresh()

        return response

    async def async_lock_action(self, entity_id: str, action: ADCLockCommand) -> bool:
        """Do something with a lock."""

        if entity_id not in self.devices.get("lock_ids", {}) or action not in [
            ADCLockCommand.LOCK,
            ADCLockCommand.UNLOCK,
        ]:
            return False

        return await self._async_send_action(entity_id, action, ADCDeviceType.LOCK)

    async def async_partition_action(
        self, entity_id: str, action: ADCPartitionCommand
    ) -> bool:
        """Do something with a partition."""

        if entity_id not in self.devices.get("partition_ids", {}) or action not in [
            ADCPartitionCommand.ARM_STAY,
            ADCPartitionCommand.DISARM,
            ADCPartitionCommand.ARM_NIGHT,
            ADCPartitionCommand.ARM_AWAY,
        ]:
            return False

        return await self._async_send_action(entity_id, action, ADCDeviceType.PARTITION)

    async def async_garage_door_action(self, entity_id: str, action: str) -> bool:
        """Do something with a garage door."""

        if entity_id not in self.devices.get("garage_door_ids", {}) or action not in [
            ADCGarageDoorCommand.OPEN,
            ADCGarageDoorCommand.CLOSE,
        ]:
            return False

        return await self._async_send_action(
            entity_id, action, ADCDeviceType.GARAGE_DOOR
        )


async def get_controller(
    hass: HomeAssistant,
    username: str,
    password: str,
    twofactorcookie: str,
    forcebypass: adci.ADCIArmingOption | None = None,
    noentrydelay: adci.ADCIArmingOption | None = None,
    silentarming: adci.ADCIArmingOption | None = None,
) -> ADCController:
    """Create an alarm controller object and log in."""
    try:
        controller = ADCController(
            username=username,
            password=password,
            websession=async_get_clientsession(hass),
            forcebypass=adci.ADCIArmingOption(forcebypass).to_adc
            if forcebypass is not None
            else adci.ADCIArmingOption.NEVER.value,
            noentrydelay=adci.ADCIArmingOption(noentrydelay).to_adc
            if noentrydelay is not None
            else adci.ADCIArmingOption.NEVER.value,
            silentarming=adci.ADCIArmingOption(silentarming).to_adc
            if silentarming is not None
            else adci.ADCIArmingOption.NEVER.value,
            twofactorcookie=twofactorcookie,
        )

        async with async_timeout.timeout(10):
            await controller.async_login()

    except ConnectionError as err:
        log.debug(
            "%s: get_controller failed with CannotConnect exception: %s",
            __name__,
            err,
        )
        raise err
    except AuthenticationFailed as err:
        log.debug(
            "%s: get_controller failed with InvalidAuth exception: %s",
            __name__,
            err,
        )
        raise err

    return controller
