"""The alarmdotcom integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .alarm_control_panel import IntAlarmControlPanel
from .base_device import IntConfigOnlyDeviceDataStructure
from .base_device import IntSystemDataStructure
from .binary_sensor import IntBinarySensor
from .const import CONF_ARM_AWAY
from .const import CONF_ARM_CODE
from .const import CONF_ARM_HOME
from .const import CONF_ARM_NIGHT
from .const import DEBUG_REQ_EVENT
from .const import DOMAIN
from .const import SENSOR_SUBTYPE_BLACKLIST
from .const import STARTUP_MESSAGE
from .controller import IntController
from .controller import IntCoordinatorDataStructure
from .cover import IntCover
from .light import IntLight
from .lock import IntLock

log = logging.getLogger(__name__)

PLATFORMS: list[str] = [
    "alarm_control_panel",
    "binary_sensor",
    "lock",
    "cover",
    "light",
    "button",
    "number",
]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up alarmdotcom controller from a config entry."""

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

    controller = IntController(hass, config_entry)
    coordinator: DataUpdateCoordinator = await controller.async_setup()
    if not coordinator:
        log.error("%s: Failed to initialize controller.", __name__)
        return False

    log.debug("Alarmdotcom config options %s", dict(config_entry.options))

    #
    # Delete devices from Home Assistant that are no longer present on Alarm.com.
    #

    # Get devices from Alarm.com
    device_ids_via_adc: set[str] = set()
    for device_id in coordinator.data.get("entity_data", []):
        device_ids_via_adc.add(device_id)

    log.debug(device_ids_via_adc)

    # Delete mobile phones from device_ids_via_adc.
    # These devices may have been added to Home Assistant before v0.2.3. Mobile phones are used for pin-less disarming on some panels but provide no value in Home Assistant.
    for sensor_id in coordinator.data.get("sensor_ids", []):
        device: (
            IntCover.DataStructure
            | IntSystemDataStructure
            | IntBinarySensor.DataStructure
            | IntLock.DataStructure
            | IntLight.DataStructure
            | IntAlarmControlPanel.DataStructure
            | None
        ) = coordinator.data.get("entity_data", {}).get(sensor_id)

        if (
            device is not None
            and device.get("device_subtype") in SENSOR_SUBTYPE_BLACKLIST
        ):
            log.debug(
                "Removing blacklisted sensor %s (%s) from Home Assistant.",
                device.get("name"),
                device.get("unique_id"),
            )
            device_ids_via_adc.remove(sensor_id)

    # Will be used during virtual device creation.
    device_ids_via_hass: set[str] = set()

    # Compare against device registry
    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    ):
        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN and identifier[1] in device_ids_via_adc:
                device_ids_via_hass.add(identifier[1])
                break

            log.debug(
                "Removing orphaned device %s (%s | %s)",
                device_entry.name,
                device_entry.identifiers,
                device_entry.id,
            )

            device_registry.async_remove_device(device_entry.id)

    # Store coordinator
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    # Create virtual DEVICES.
    # Currently, only Skybell cameras are virtual devices. We support modifying configuration attributes but not viewing video.
    master_device_data: IntCoordinatorDataStructure = coordinator.data
    for camera_id in master_device_data.get("camera_ids", []):
        camera_data: IntConfigOnlyDeviceDataStructure | None = master_device_data.get(
            "entity_data", {}
        ).get(camera_id)

        # Check if camera already created.
        if camera_id in device_ids_via_hass:
            continue

        if not camera_data:
            log.warning("Couldn't find data for camera ID %s", camera_id)
            continue

        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, mac_address)}
            if (mac_address := camera_data.get("mac_address"))
            else None,
            identifiers={(DOMAIN, camera_data.get("unique_id"))},
            name=camera_data.get("name"),
            model=camera_data.get("model"),
            manufacturer=camera_data.get("manufacturer"),
        )

    # Create real devices
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    async def handle_alarmdotcom_debug_request_event(event: Event) -> None:
        """Dump debug data when requested via Home Assistant event."""

        entity_data = coordinator.data.get("entity_data", {}).get(
            event.data.get("device_id"), {}
        )

        log.warning(
            "ALARM.COM DEBUG DATA FOR %s: %s",
            entity_data.get("name", "").upper(),
            entity_data,
        )

    hass.bus.async_listen(DEBUG_REQ_EVENT, handle_alarmdotcom_debug_request_event)

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    if config_entry.version == 1:

        log.debug("Migrating from version %s", config_entry.version)

        v2_options: ConfigEntry = {**config_entry.options}

        v2_options["use_arm_code"] = bool(config_entry.options.get(CONF_ARM_CODE))

        v2_options[CONF_ARM_CODE] = (
            str(arm_code)
            if (arm_code := config_entry.options.get(CONF_ARM_CODE))
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
            v3_options[CONF_ARM_CODE] = None

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
