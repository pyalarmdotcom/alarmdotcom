"""The alarmdotcom integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import const as adci
from .controller import ADCIController

log = logging.getLogger(__name__)

PLATFORMS: list[str] = [
    "alarm_control_panel",
    "binary_sensor",
    "lock",
    "cover",
    "light",
    "button",
]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up alarmdotcom controller from a config entry."""

    log.debug("%s: Initializing Alarmdotcom from config entry.", __name__)

    # As there currently is no way to import options from yaml
    # when setting up a config entry, we fallback to adding
    # the options to the config entry and pull them out here if
    # they are missing from the options.
    _async_import_options_from_data_if_missing(hass, config_entry)

    hass.data.setdefault(adci.DOMAIN, {})

    if adci.DOMAIN not in hass.data:
        # Print startup message
        log.info(adci.STARTUP_MESSAGE)

    controller = ADCIController(hass, config_entry)
    if not await controller.async_setup():
        log.error("%s: Failed to initialize controller.", __name__)
        return False

    log.debug("Alarmdotcom config options %s", dict(config_entry.options))

    #
    # Delete devices from Home Assistant that are no longer present on Alarm.com.
    #

    # Get devices from Alarm.com
    current_device_ids: set[str] = set()
    for device_id in controller.devices.get("entity_data", []):
        current_device_ids.add(device_id)

    log.debug(current_device_ids)

    # Delete mobile phones from current_device_ids.
    # These devices may have been added to Home Assistant before v0.2.3. Mobile phones are used for pin-less disarming on some panels but provide no value in Home Assistant.
    for sensor_id in controller.devices.get("sensor_ids", []):
        device: (
            adci.ADCIGarageDoorData
            | adci.ADCISystemData
            | adci.ADCISensorData
            | adci.ADCILockData
            | adci.ADCILightData
            | adci.ADCIPartitionData
            | None
        ) = controller.devices.get("entity_data", {}).get(sensor_id)

        if (
            device is not None
            and device.get("device_subtype") in adci.SENSOR_SUBTYPE_BLACKLIST
        ):
            log.debug(
                "Removing blacklisted sensor %s (%s) from Home Assistant.",
                device.get("name"),
                device.get("unique_id"),
            )
            current_device_ids.remove(sensor_id)

    # Compare against device registry
    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    ):
        for identifier in device_entry.identifiers:
            if identifier[0] == adci.DOMAIN:
                if (
                    identifier[1] in current_device_ids
                    or f"{identifier[1]}_low_battery" in current_device_ids
                    or f"{identifier[1]}_malfunction" in current_device_ids
                    or f"{identifier[1]}_debug" in current_device_ids
                ):

                    break

                log.debug(
                    "Removing orphaned device %s (%s | %s)",
                    device_entry.name,
                    device_entry.identifiers,
                    device_entry.id,
                )

                device_registry.async_remove_device(device_entry.id)

    # Store controller
    hass.data[adci.DOMAIN][config_entry.entry_id] = controller

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    async def handle_alarmdotcom_debug_request_event(event: Event) -> None:
        """Dump debug data when requested via Home Assistant event."""

        entity_data = controller.devices.get("entity_data", {}).get(event.data.get("device_id"), {})  # type: ignore

        log.warning(
            "ALARM.COM DEBUG DATA FOR %s: %s",
            entity_data.get("name", "").upper(),
            entity_data,
        )

    hass.bus.async_listen(adci.DEBUG_REQ_EVENT, handle_alarmdotcom_debug_request_event)

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    if config_entry.version == 1:

        log.debug("Migrating from version %s", config_entry.version)

        v2_options: ConfigEntry = {**config_entry.options}

        v2_options["use_arm_code"] = bool(config_entry.options.get(adci.CONF_ARM_CODE))

        v2_options[adci.CONF_ARM_CODE] = (
            str(arm_code)
            if (arm_code := config_entry.options.get(adci.CONF_ARM_CODE))
            else ""
        )

        config_entry.version = 2

        hass.config_entries.async_update_entry(
            config_entry, data={**config_entry.data}, options=v2_options
        )

        log.info("Migration to version %s successful", config_entry.version)

    if config_entry.version == 2:

        log.debug("Migrating from version %s", config_entry.version)

        v3_options: ConfigEntry = {**config_entry.options}

        if not v3_options.get("use_arm_code"):
            v3_options[adci.CONF_ARM_CODE] = None

        # Populate Arm Home
        new_arm_home = []

        if v3_options.get("force_bypass") in ["Stay Only", "Always"]:
            new_arm_home.append("bypass")
        if v3_options.get("silent_arming") in ["Stay Only", "Always"]:
            new_arm_home.append("silent")
        if v3_options.get("no_entry_delay") not in ["Stay Only", "Always"]:
            new_arm_home.append("delay")

        v3_options[adci.CONF_ARM_HOME] = new_arm_home

        # Populate Arm Away
        new_arm_away = []

        if v3_options.get("force_bypass") in ["Away Only", "Always"]:
            new_arm_away.append("bypass")
        if v3_options.get("silent_arming") in ["Away Only", "Always"]:
            new_arm_away.append("silent")
        if v3_options.get("no_entry_delay") not in ["Away Only", "Always"]:
            new_arm_away.append("delay")

        v3_options[adci.CONF_ARM_AWAY] = new_arm_away

        # Populate Arm Night
        new_arm_night = []

        if v3_options.get("force_bypass") == "Always":
            new_arm_night.append("bypass")
        if v3_options.get("silent_arming") == "Always":
            new_arm_night.append("silent")
        if v3_options.get("no_entry_delay") != "Always":
            new_arm_night.append("delay")

        v3_options[adci.CONF_ARM_NIGHT] = new_arm_night

        config_entry.version = 3

        # Purge deprecated config options.

        if v3_options.get("use_arm_code"):
            v3_options["use_arm_code"] = None
        if v3_options.get("force_bypass"):
            v3_options["force_bypass"] = None
        if v3_options.get("silent_arming"):
            v3_options["silent_arming"] = None
        if v3_options.get("no_entry_delay"):
            v3_options["no_entry_delay"] = None

        hass.config_entries.async_update_entry(
            config_entry, data={**config_entry.data}, options=v3_options
        )

        log.info("Migration to version %s successful", config_entry.version)

    return True


def _async_import_options_from_data_if_missing(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Import options from configuration.yaml."""

    options = dict(entry.options)
    data = {}
    importable_options = [
        "force_bypass",
        "no_entry_delay",
        "silent_arming",
        "code",
    ]
    found = False
    for key in entry.data:
        if key in importable_options and key not in options:
            options[key] = entry.data[key]
            found = True
        else:
            data[key] = entry.data[key]

    if found:
        hass.config_entries.async_update_entry(entry, data=data, options=options)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok: bool = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        log.debug("%s: Unloaded Alarm.com config entry.", __name__)
        hass.data[adci.DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class ADCIEntity(CoordinatorEntity):  # type: ignore
    """Base class for ADC entities."""

    def __init__(
        self,
        controller: ADCIController,
        device_data: Any,
    ) -> None:
        """Initialize class."""
        super().__init__(controller._coordinator)
        self._controller: ADCIController = controller
        self._device = device_data

        self._attr_unique_id = device_data["unique_id"]
        self._attr_name = device_data["name"]

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return entity specific state attributes."""

        return {
            "mac_address": self._device.get("mac_address"),
            "raw_state_text": self._device.get("raw_state_text"),
        }

    @property
    def device_info(self) -> dict:
        """Return the device information."""

        return {
            "default_manufacturer": "Alarm.com",
            "name": self.name,
            "identifiers": {(adci.DOMAIN, self._device.get("unique_id"))},
            "via_device": (adci.DOMAIN, self._device.get("parent_id")),
        }

    async def async_added_to_hass(self) -> None:
        """Register updater for self._device when entity is added to Home Assistant."""
        # First, get updated state data.
        self.async_on_remove(
            self.coordinator.async_add_listener(self._update_device_data)
        )

        # Second, ask super to announce state update.
        await super().async_added_to_hass()

    def _update_device_data(self) -> None:

        updated = False

        try:
            device_data: dict | adci.ADCIGarageDoorData | adci.ADCILockData | adci.ADCIPartitionData | adci.ADCISensorData | adci.ADCISystemData | adci.ADCILightData = self._controller.devices.get(
                "entity_data", {}
            ).get(
                self.unique_id, {}
            )
            self._device = device_data

            updated = True

        except KeyError as err:
            log.error(
                "%s: Device database update failed for %s.", __name__, self._device
            )
            raise UpdateFailed from err

        if not updated:
            err_msg = (
                f"{__name__}: Failed to update data for {self._device.get('name')}."
            )

            log.error(err_msg)
            log.debug(device_data)

            raise UpdateFailed(err_msg)

    def _show_permission_error(self, action: str = "") -> None:
        """Show Home Assistant notification to alert user that they lack permission to perform action."""

        # TODO: This notification needs work. Actions should be user-readable. Device type should be a HA device type (alarm control panel instead of partition). Device name should be shown.
        error_msg = (
            "Your Alarm.com user does not have permission to"
            f" {action} your {self._attr_device_class.lower()}. Please log"
            " in to Alarm.com to grant the appropriate permissions to your"
            " account."
        )
        persistent_notification.async_create(
            self.hass,
            error_msg,
            title="Alarm.com Error",
            notification_id="alarmcom_permission_error",
        )
