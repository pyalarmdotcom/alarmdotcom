"""The alarmdotcom integration."""

import logging

import aiohttp
import pyalarmdotcomajax as pyadc
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    CONF_ARM_AWAY,
    CONF_ARM_HOME,
    CONF_ARM_NIGHT,
    CONF_FORCE_BYPASS,
    CONF_NO_ENTRY_DELAY,
    CONF_SILENT_ARM,
    DATA_HUB,
    DEBUG_REQ_EVENT,
    DOMAIN,
    PLATFORMS,
    STARTUP_MESSAGE,
)
from .hub import AlarmHub

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up alarmdotcom hub from a config entry."""

    LOGGER.info("%s: Initializing Alarmdotcom from config entry.", __name__)

    LOGGER.info(STARTUP_MESSAGE)

    #
    # Initialize Alarm.com Connection & Data Update Coordinator
    #

    hub = AlarmHub(hass, config_entry)

    try:
        await hub.initialize()
    except pyadc.AuthenticationException as ex:
        raise ConfigEntryAuthFailed from ex
    except (TimeoutError, pyadc.AlarmdotcomException, aiohttp.ClientError) as ex:
        raise ConfigEntryNotReady from ex

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def handle_alarmdotcom_debug_request_event(event: Event) -> None:
        """Dump debug data when requested via Home Assistant event."""

        event_resource = hub.api.resources.get(str(event.data.get("resource_id")))

        if event_resource is None:
            LOGGER.warning(
                "ALARM.COM DEBUG DATA FOR %s: No such device.",
                str(event.data.get("resource_id")).upper(),
            )
            return

        LOGGER.warning(
            "ALARM.COM DEBUG DATA FOR %s: %s",
            str(event_resource.attributes.description).upper(),
            event_resource.api_resource.to_json(),
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

        v2_options["arm_code"] = (
            str(arm_code) if (arm_code := config_entry.options.get("arm_code")) else ""
        )

        hass.config_entries.async_update_entry(
            config_entry, data={**config_entry.data}, options=v2_options, version=2
        )

        LOGGER.info("Migration to version %s successful", 2)

    #
    # To v3
    #

    if config_entry.version == 2:
        LOGGER.debug("Migrating from version %s", config_entry.version)

        v3_options = {**config_entry.options}

        if not v3_options.get("use_arm_code"):
            v3_options["arm_code"] = None

        # Populate Arm Home
        new_arm_home: list[str] = []

        if v3_options.get("force_bypass") in ["Stay Only", "Always"]:
            new_arm_home.append("bypass")
        if v3_options.get("silent_arming") in ["Stay Only", "Always"]:
            new_arm_home.append("silent")
        if v3_options.get("no_entry_delay") not in ["Stay Only", "Always"]:
            new_arm_home.append("delay")

        v3_options[CONF_ARM_HOME] = new_arm_home

        # Populate Arm Away
        new_arm_away: list[str] = []

        if v3_options.get("force_bypass") in ["Away Only", "Always"]:
            new_arm_away.append("bypass")
        if v3_options.get("silent_arming") in ["Away Only", "Always"]:
            new_arm_away.append("silent")
        if v3_options.get("no_entry_delay") not in ["Away Only", "Always"]:
            new_arm_away.append("delay")

        v3_options[CONF_ARM_AWAY] = new_arm_away

        # Populate Arm Night
        new_arm_night: list[str] = []

        if v3_options.get("force_bypass") == "Always":
            new_arm_night.append("bypass")
        if v3_options.get("silent_arming") == "Always":
            new_arm_night.append("silent")
        if v3_options.get("no_entry_delay") != "Always":
            new_arm_night.append("delay")

        v3_options[CONF_ARM_NIGHT] = new_arm_night

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
            config_entry, data={**config_entry.data}, options=v3_options, version=3
        )

        LOGGER.info("Migration to version %s successful", 3)

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

        hass.config_entries.async_update_entry(
            config_entry, data={**config_entry.data}, options=v4_options, version=4
        )

        LOGGER.info("Migration to version %s successful", 4)

    #
    # To v5
    #

    if config_entry.version == 4:
        LOGGER.debug("Migrating from version %s", config_entry.version)

        v5_options: dict = {**config_entry.options}

        # Remove deprecated config options for v5.
        v5_options.pop("update_interval", None)
        v5_options.pop("ws_reconnect_timeout", None)

        hass.config_entries.async_update_entry(
            config_entry, data={**config_entry.data}, options=v5_options, version=5
        )

        LOGGER.info("Migration to version %s successful", 5)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    hub: AlarmHub = hass.data[DOMAIN].pop(config_entry.entry_id)[DATA_HUB]

    unload_success = await hub.close()

    if len(hass.data[DOMAIN]) == 0:
        hass.data.pop(DOMAIN)
        # hass.services.async_remove(DOMAIN, SERVICES)

    return unload_success
