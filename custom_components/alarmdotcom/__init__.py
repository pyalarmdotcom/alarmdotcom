"""The alarmdotcom integration."""
from __future__ import annotations

import json
import logging
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .alarmhub import AlarmHub
from .const import CONF_ARM_AWAY
from .const import CONF_ARM_HOME
from .const import CONF_ARM_NIGHT
from .const import DEBUG_REQ_EVENT
from .const import DOMAIN
from .const import STARTUP_MESSAGE

log = logging.getLogger(__name__)

PLATFORMS: list[str] = [
    "alarm_control_panel",
    "binary_sensor",
    "lock",
    "cover",
    "light",
    "button",
    "number",
    "switch",
    "select",
    "climate",
]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up alarmdotcom alarmhub from a config entry."""

    log.debug("%s: Initializing Alarmdotcom from config entry.", __name__)

    # As there currently is no way to import options from yaml
    # when setting up a config entry, we fallback to adding
    # the options to the config entry and pull them out here if
    # they are missing from the options.
    _async_import_options_from_data_if_missing(hass, config_entry)

    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in hass.data:
        # Print startup message
        log.info(STARTUP_MESSAGE)

    alarmhub = AlarmHub(hass, config_entry)
    await alarmhub.async_setup()

    if not alarmhub.coordinator:
        log.error("%s: Failed to initialize alarmhub.", __name__)
        return False

    log.debug("Alarmdotcom config options %s", dict(config_entry.options))

    #
    # Delete devices from Home Assistant that are no longer present on Alarm.com.
    #

    # Get devices from Alarm.com
    device_ids_via_adc: set[str] = set()
    for device in alarmhub.devices:
        device_ids_via_adc.add(device.id_)

    log.debug(device_ids_via_adc)

    # Will be used during virtual device creation.
    device_ids_via_hass: set[str] = set()

    # Compare against device registry
    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    ):
        for identifier in device_entry.identifiers:

            # Remove _debug, _malfunction, etc. from IDs
            id_matches = re.search(r"([0-9]+-[0-9]+)(?:_[a-zA-Z_]+)*", identifier[1])

            if (
                id_matches is not None
                and identifier[0] == DOMAIN
                and id_matches.group(1) in device_ids_via_adc
            ):
                device_ids_via_hass.add(identifier[1])
                break

            log.debug(
                "Removing orphaned device %s (%s | %s)",
                device_entry.name,
                device_entry.identifiers,
                device_entry.id,
            )

            device_registry.async_remove_device(device_entry.id)

    # Store alarmhub
    hass.data[DOMAIN][config_entry.entry_id] = alarmhub

    # Create virtual DEVICES.
    # Currently, only Skybell cameras are virtual devices. We support modifying configuration attributes but not viewing video.
    for camera in alarmhub.system.cameras:

        # Check if camera already created.
        if camera.id_ in device_ids_via_hass:
            continue

        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, camera.mac_address)},
            identifiers={(DOMAIN, camera.id_)},
            name=camera.name,
            model="Skybell HD",
            manufacturer="Skybell",
        )

    # Create real devices
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    async def handle_alarmdotcom_debug_request_event(event: Event) -> None:
        """Dump debug data when requested via Home Assistant event."""

        device = alarmhub.system.get_device_by_id(event.data.get("device_id"))

        if device:
            log.warning(
                "ALARM.COM DEBUG DATA FOR %s: %s",
                device.name.upper(),
                json.dumps(device.debug_data),
            )

    hass.bus.async_listen(DEBUG_REQ_EVENT, handle_alarmdotcom_debug_request_event)

    log.debug("%s: Finished initializing Alarmdotcom from config entry.", __name__)

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    #
    # To v2
    #

    if config_entry.version == 1:

        log.debug("Migrating from version %s", config_entry.version)

        v2_options: ConfigEntry = {**config_entry.options}

        v2_options["use_arm_code"] = bool(config_entry.options.get("arm_code"))

        v2_options["arm_code"] = (
            str(arm_code) if (arm_code := config_entry.options.get("arm_code")) else ""
        )

        config_entry.version = 2

        hass.config_entries.async_update_entry(
            config_entry, data={**config_entry.data}, options=v2_options
        )

        log.info("Migration to version %s successful", config_entry.version)

    #
    # To v3
    #

    if config_entry.version == 2:

        log.debug("Migrating from version %s", config_entry.version)

        v3_options: ConfigEntry = {**config_entry.options}

        if not v3_options.get("use_arm_code"):
            v3_options["arm_code"] = None

        # Populate Arm Home
        new_arm_home = []

        if v3_options.get("force_bypass") in ["Stay Only", "Always"]:
            new_arm_home.append("bypass")
        if v3_options.get("silent_arming") in ["Stay Only", "Always"]:
            new_arm_home.append("silent")
        if v3_options.get("no_entry_delay") not in ["Stay Only", "Always"]:
            new_arm_home.append("delay")

        v3_options[CONF_ARM_HOME] = new_arm_home

        # Populate Arm Away
        new_arm_away = []

        if v3_options.get("force_bypass") in ["Away Only", "Always"]:
            new_arm_away.append("bypass")
        if v3_options.get("silent_arming") in ["Away Only", "Always"]:
            new_arm_away.append("silent")
        if v3_options.get("no_entry_delay") not in ["Away Only", "Always"]:
            new_arm_away.append("delay")

        v3_options[CONF_ARM_AWAY] = new_arm_away

        # Populate Arm Night
        new_arm_night = []

        if v3_options.get("force_bypass") == "Always":
            new_arm_night.append("bypass")
        if v3_options.get("silent_arming") == "Always":
            new_arm_night.append("silent")
        if v3_options.get("no_entry_delay") != "Always":
            new_arm_night.append("delay")

        v3_options[CONF_ARM_NIGHT] = new_arm_night

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

    #
    # To v4
    #

    # Be sure to include the commented out cleanup code below when creating and migrating to config v4.

    # if config_entry.version == 3:

    #     log.debug("Migrating from version %s", config_entry.version)

    #     v4_options: dict = {**config_entry.options}

    #     # Purge config options deprecated and set to None in v3 migration.
    #     v4_options.pop("use_arm_code", None)
    #     v4_options.pop("force_bypass", None)
    #     v4_options.pop("silent_arming", None)
    #     v4_options.pop("no_entry_delay", None)

    #     config_entry.version = 4

    #     hass.config_entries.async_update_entry(
    #         config_entry, data={**config_entry.data}, options=v4_options
    #     )

    #     log.info("Migration to version %s successful", config_entry.version)

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
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
