"""The alarmdotcom integration."""
from __future__ import annotations

import asyncio
import json
import logging
import re

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from pyalarmdotcomajax import OtpRequired
from pyalarmdotcomajax.exceptions import (
    AlarmdotcomException,
    AuthenticationFailed,
    ConfigureTwoFactorAuthentication,
)

from .const import (
    CONF_ARM_AWAY,
    CONF_ARM_HOME,
    CONF_ARM_NIGHT,
    CONF_FORCE_BYPASS,
    CONF_NO_ENTRY_DELAY,
    CONF_SILENT_ARM,
    DATA_CONTROLLER,
    DEBUG_REQ_EVENT,
    DOMAIN,
    PLATFORMS,
    SENSOR_SUBTYPE_BLACKLIST,
    STARTUP_MESSAGE,
)
from .controller import AlarmIntegrationController

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up alarmdotcom hub from a config entry."""

    LOGGER.info("%s: Initializing Alarmdotcom from config entry.", __name__)

    if DOMAIN not in hass.data:
        # Print startup message
        LOGGER.info(STARTUP_MESSAGE)

    hass.data.setdefault(DOMAIN, {})

    #
    # Initialize Alarm.com Connection & Data Update Coordinator
    #

    controller = AlarmIntegrationController(hass, config_entry)

    try:
        await controller.initialize()
    except (OtpRequired, AuthenticationFailed) as ex:
        raise ConfigEntryAuthFailed("Authentication failed. Please try logging in again.") from ex
    except ConfigureTwoFactorAuthentication as ex:
        raise ConfigEntryAuthFailed from ex
    except (AlarmdotcomException, aiohttp.ClientError, asyncio.TimeoutError) as ex:
        raise ConfigEntryNotReady from ex

    # Store integration data for use during platform setup.
    hass.data[DOMAIN][config_entry.entry_id] = {
        DATA_CONTROLLER: controller,
    }

    #
    # Initialize WebSocket listener
    #

    controller.api.start_websocket()

    config_entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, controller.stop))

    #
    # Delete devices from Home Assistant that are no longer present on Alarm.com.
    #

    device_registry = dr.async_get(hass)

    # Get devices from Alarm.com
    device_ids_via_adc: set[str] = set()
    for device in controller.api.devices.all.values():
        if device.device_subtype not in SENSOR_SUBTYPE_BLACKLIST and device.has_state:
            device_ids_via_adc.add(device.id_)

    # Purge deleted devices from Home Assistant
    for deleted_device in list(device_registry.deleted_devices.values()):
        for identifier in deleted_device.identifiers:
            if identifier[0] == DOMAIN:
                LOGGER.info("Removing orphaned device from Home Assistant: %s", deleted_device.identifiers)
                del device_registry.deleted_devices[deleted_device.id]

    # Will be used during virtual device creation.
    device_ids_via_hass: set[str] = set()

    # Compare against device registry
    for device_entry in dr.async_entries_for_config_entry(device_registry, config_entry.entry_id):
        for identifier in device_entry.identifiers:
            if identifier[1] is None:
                continue

            matched_id: str

            try:
                # Remove _debug, _malfunction, etc. from IDs
                id_matches = re.search(r"([0-9]+-[0-9]+)(?:_[a-zA-Z_]+)*", identifier[1])
            except TypeError:
                matched_id = identifier[1]
            else:
                if id_matches is not None:
                    matched_id = id_matches.group(1)

            if id_matches is not None and identifier[0] == DOMAIN and matched_id in device_ids_via_adc:
                device_ids_via_hass.add(identifier[1])
                break

            LOGGER.info(
                "Removing device no longer present on Alarm.com: %s (%s | %s)",
                device_entry.name,
                device_entry.identifiers,
                device_entry.id,
            )

            device_registry.async_remove_device(device_entry.id)

    # Create virtual DEVICES.
    # Currently, only Skybell cameras are virtual devices. We support modifying configuration attributes but not viewing video.
    for camera in controller.api.devices.cameras.values():
        # Check if camera already created.
        if camera.id_ in device_ids_via_hass:
            continue

        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, str(camera.mac_address))},
            identifiers={(DOMAIN, camera.id_)},
            name=camera.name,
            model="Skybell HD",
            manufacturer="Skybell",
        )

    # Create real devices
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def handle_alarmdotcom_debug_request_event(event: Event) -> None:
        """Dump debug data when requested via Home Assistant event."""

        event_device = controller.api.devices.get(str(event.data.get("device_id")))

        LOGGER.warning(
            "ALARM.COM DEBUG DATA FOR %s: %s",
            str(event_device.name).upper(),
            json.dumps(event_device.debug_data),
        )

    # Listen for debug entity requests
    hass.bus.async_listen(DEBUG_REQ_EVENT, handle_alarmdotcom_debug_request_event)

    LOGGER.info("%s: Finished initializing Alarmdotcom from config entry.", __name__)

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    #
    # To v2
    #

    if config_entry.version == 1:
        LOGGER.debug("Migrating from version %s", config_entry.version)

        v2_options = {**config_entry.options}

        v2_options["use_arm_code"] = bool(config_entry.options.get("arm_code"))

        v2_options["arm_code"] = str(arm_code) if (arm_code := config_entry.options.get("arm_code")) else ""

        config_entry.version = 2

        hass.config_entries.async_update_entry(config_entry, data={**config_entry.data}, options=v2_options)

        LOGGER.info("Migration to version %s successful", config_entry.version)

    #
    # To v3
    #

    if config_entry.version == 2:
        LOGGER.debug("Migrating from version %s", config_entry.version)

        v3_options = {**config_entry.options}

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

        hass.config_entries.async_update_entry(config_entry, data={**config_entry.data}, options=v3_options)

        LOGGER.info("Migration to version %s successful", config_entry.version)

    #
    # To v4
    #

    if config_entry.version == 3:
        LOGGER.debug("Migrating from version %s", config_entry.version)

        v4_options: dict = {**config_entry.options}

        # Purge config options deprecated and set to None in v3 migration.
        v4_options.pop("use_arm_code", None)
        v4_options.pop("force_bypass", None)
        v4_options.pop("silent_arming", None)
        v4_options.pop("no_entry_delay", None)

        # Make config option names more explicit. This allows for future rollout of selective bypass when arming.
        for arm_mode in (CONF_ARM_HOME, CONF_ARM_AWAY, CONF_ARM_NIGHT):
            if arm_mode in v4_options:
                if "bypass" in v4_options[arm_mode]:
                    v4_options[arm_mode].remove("bypass")
                    v4_options[arm_mode].append(CONF_FORCE_BYPASS)
                if "silent" in v4_options[arm_mode]:
                    v4_options[arm_mode].remove("silent")
                    v4_options[arm_mode].append(CONF_SILENT_ARM)
                if "delay" in v4_options[arm_mode]:
                    v4_options[arm_mode].remove("delay")
                    v4_options[arm_mode].append(CONF_NO_ENTRY_DELAY)

        config_entry.version = 4

        hass.config_entries.async_update_entry(config_entry, data={**config_entry.data}, options=v4_options)

        LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    controller: AlarmIntegrationController = hass.data[DOMAIN].pop(config_entry.entry_id)[DATA_CONTROLLER]

    controller.api.stop_websocket()
    controller.stop_keep_alive()

    unload_ok: bool = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if unload_ok:
        LOGGER.debug("%s: Unloaded Alarm.com config entry.", __name__)

    return unload_ok
