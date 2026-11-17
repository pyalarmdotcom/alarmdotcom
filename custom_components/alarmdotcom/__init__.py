"""The alarmdotcom integration."""

import os
import sys
from pathlib import Path

# pyalarmdotcomajax is vendored directly in this directory, as the
# _pyalarmdotcomajax package (custom_components/alarmdotcom/_pyalarmdotcomajax/),
# rather than installed as a separate pip package. This avoids the git+
# dependency in manifest.json that blocked full HACS/hassfest compliance and
# required lockstep version bumps across two repos for every fix.
#
# It's imported and referenced everywhere as _pyalarmdotcomajax (leading
# underscore), not pyalarmdotcomajax, deliberately: no legitimate PyPI package
# can use a leading underscore, so this name can never collide with a stray
# pip-installed pyalarmdotcomajax left over from before this vendoring change
# (or from anything else). A collision like that previously meant a missing
# or broken vendored copy could silently fall back to a stale pip-installed
# copy instead of failing - this rename makes that fall-back impossible: if
# _pyalarmdotcomajax isn't on sys.path, importing it can only ever raise
# ModuleNotFoundError, never silently resolve to the wrong thing.
#
# The vendored package's internal modules still use absolute imports (e.g.
# `from _pyalarmdotcomajax.controllers.users import ...`), so this directory
# is added to sys.path here, before anything imports _pyalarmdotcomajax, so
# those imports resolve without needing every internal file rewritten to
# relative imports.
_VENDOR_PATH = os.path.dirname(__file__)
if _VENDOR_PATH not in sys.path:
    sys.path.append(_VENDOR_PATH)

import logging
from dataclasses import dataclass
from datetime import timedelta

import _pyalarmdotcomajax as pyadc
import aiohttp
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .access_service import (
    SERVICE_GET_TEMPORARY_USER_SCHEDULE,
    SERVICE_SET_TEMPORARY_ACCESS,
    async_register_access_service,
)
from .activity_history import ActivityFeedTracker
from .auto_off import AutoOffManager
from .camera_api import AlarmCameraSession
from .const import (
    ATTR_DURATION,
    ATTR_PARTITION_ID,
    ATTR_RESOURCE_ID,
    CONF_ARM_AWAY,
    CONF_ARM_HOME,
    CONF_ARM_NIGHT,
    CONF_FORCE_BYPASS,
    CONF_MFA_TOKEN,
    CONF_NO_ENTRY_DELAY,
    CONF_SILENT_ARM,
    DEBUG_REQ_EVENT,
    DOMAIN,
    PLATFORMS,
    SERVICE_BYPASS_SENSOR,
    SERVICE_CANCEL_AUTO_OFF,
    SERVICE_SET_AUTO_OFF,
    SERVICE_UNBYPASS_SENSOR,
    STARTUP_MESSAGE,
)
from .hub import AlarmHub
from .schema import vol
from .webrtc_ws import async_register as async_register_webrtc

LOGGER = logging.getLogger(__name__)


@dataclass
class AlarmEntryData:
    """Runtime data stored on config_entry.runtime_data for this integration."""

    hub: AlarmHub
    auto_off_manager: AutoOffManager
    camera_session: AlarmCameraSession | None
    activity_feed_tracker: ActivityFeedTracker


def _log_pyadc_location() -> None:
    """
    Log which pyalarmdotcomajax copy actually loaded, warning if it's not the vendored one.

    Pure path-string operations (join/abspath/normcase never touch the
    filesystem for a path that's already resolved via a live module's
    __file__), pulled into its own sync function rather than left inline
    in async_setup_entry - it has no genuine async/await need.
    """
    pyadc_version = getattr(pyadc, "__version__", "unknown")
    expected_pyadc_path = os.path.join(_VENDOR_PATH, "_pyalarmdotcomajax", "__init__.py")
    resolved_pyadc_path = os.path.normcase(os.path.abspath(pyadc.__file__))
    if resolved_pyadc_path != os.path.normcase(os.path.abspath(expected_pyadc_path)):
        LOGGER.warning(
            "pyalarmdotcomajax %s loaded from an UNEXPECTED location: %s "
            "(expected the bundled copy at: %s). This usually means a leftover "
            "pip-installed pyalarmdotcomajax from before this integration vendored "
            "it directly (harmless on its own, but worth cleaning up with "
            "'pip uninstall pyalarmdotcomajax' - see the CHANGELOG for details).",
            pyadc_version,
            pyadc.__file__,
            expected_pyadc_path,
        )
    else:
        LOGGER.info("pyalarmdotcomajax loaded from the bundled copy: %s", pyadc.__file__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up alarmdotcom hub from a config entry."""

    async_register_webrtc(hass)
    if hass.http is not None and not hass.data.get(DOMAIN + "_card_static_registered"):
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                "/alarmdotcom/alarm-webrtc-card.js",
                str(Path(__file__).parent / "www" / "alarm-webrtc-card.js"),
                cache_headers=True,
            )
        ])
        hass.data[DOMAIN + "_card_static_registered"] = True
        # Storage-mode dashboards can register the card automatically. YAML
        # dashboards manage resources in YAML and are left untouched.
        try:
            lovelace = hass.data.get("lovelace")
            resources = getattr(lovelace, "resources", None)
            if resources is not None and hasattr(resources, "async_load"):
                await resources.async_load()
                url = "/alarmdotcom/alarm-webrtc-card.js"
                existing = resources.async_items()
                if not any(item.get("url", "").split("?")[0] == url for item in existing):
                    await resources.async_create_item({"url": url, "res_type": "module"})
        except Exception as err:
            LOGGER.debug("Automatic camera card resource registration unavailable: %s", err)
    LOGGER.info("%s: Initializing Alarmdotcom from config entry.", __name__)
    LOGGER.info(STARTUP_MESSAGE)
    _log_pyadc_location()

    hub = AlarmHub(hass, config_entry)

    try:
        await hub.initialize()
    except pyadc.AuthenticationException as ex:
        raise ConfigEntryAuthFailed from ex
    except (TimeoutError, pyadc.AlarmdotcomException, aiohttp.ClientError) as ex:
        raise ConfigEntryNotReady from ex

    auto_off_manager = AutoOffManager(hass, config_entry.entry_id)
    await auto_off_manager.async_load()

    activity_feed_tracker = ActivityFeedTracker(hub)
    activity_feed_tracker.async_start()

    # Initialize WebRTC camera session, best effort.
    # Prefer reusing the already-authenticated pyalarmdotcomajax session to
    # avoid a second login. Falls back to an independent login automatically.
    camera_session: AlarmCameraSession | None
    try:
        camera_session = AlarmCameraSession.from_alarm_bridge(
            bridge=hub.api,
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            mfa_cookie=config_entry.data.get(CONF_MFA_TOKEN),
        )

        # Only log in when we had to create our own independent session and
        # still do not have an ajax key.
        if camera_session.owns_session and not camera_session.ajax_key:
            LOGGER.debug("Camera session: performing independent login.")
            await camera_session.login()
        else:
            LOGGER.debug(
                "Camera session: reusing pyalarmdotcomajax session, no second login needed."
            )
    except Exception as err:
        LOGGER.warning(
            "Alarm.com camera session could not be initialized: %s. "
            "Camera entities will be unavailable.",
            err,
        )
        camera_session = None

    config_entry.runtime_data = AlarmEntryData(
        hub=hub,
        auto_off_manager=auto_off_manager,
        camera_session=camera_session,
        activity_feed_tracker=activity_feed_tracker,
    )

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

        # Resource JSON can contain account details and authentication fields.
        # Never dump it into Home Assistant logs, even on a debug request.
        LOGGER.warning(
            "ALARM.COM DEBUG DATA FOR %s: resource present (payload omitted for security)",
            str(event_resource.attributes.description).upper(),
        )

    hass.bus.async_listen(DEBUG_REQ_EVENT, handle_alarmdotcom_debug_request_event)

    async_register_access_service(hass)
    _async_register_services(hass, config_entry, hub, auto_off_manager)

    LOGGER.info("%s: Finished initializing Alarmdotcom from config entry.", __name__)
    return True


def _async_register_services(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    hub: AlarmHub,
    auto_off_manager: AutoOffManager,
) -> None:
    """
    Register this config entry's bypass/unbypass and auto-off services.

    Pulled out of async_setup_entry (which was otherwise growing too complex
    for its own good) - takes the hub and auto_off_manager it needs directly
    rather than reaching back into hass.data itself, so it stays easy to
    reason about in isolation.
    """

    async def handle_bypass_service(call: ServiceCall) -> None:
        """Handle a bypass or unbypass service request."""

        resource_id = str(call.data[ATTR_RESOURCE_ID])
        partition_id = call.data.get(ATTR_PARTITION_ID)
        bypass = call.service == SERVICE_BYPASS_SENSOR

        sensor = hub.api.sensors.get(resource_id)
        if sensor is None:
            raise ServiceValidationError(
                f"No such Alarm.com sensor: {resource_id}. Check that the resource ID is correct "
                "(see the 'resource_id' attribute on the sensor entity)."
            )

        if not (sensor.attributes.supports_bypass or sensor.attributes.supports_immediate_bypass):
            raise ServiceValidationError(
                f"Alarm.com sensor does not support bypass: {resource_id}. Some panels do not expose "
                "bypass capabilities via the Alarm.com API for this sensor type."
            )

        resolved_partition_id = str(partition_id) if partition_id else None
        if resolved_partition_id is None:
            matching_partition = next(
                (
                    partition
                    for partition in hub.api.partitions
                    if partition.system_id == sensor.system_id
                ),
                None,
            )
            if matching_partition is None:
                raise ServiceValidationError(
                    f"No partition found for sensor: {resource_id}. Provide partition_id explicitly."
                )
            resolved_partition_id = matching_partition.id

        try:
            await hub.api.partitions.change_sensor_bypass(
                resolved_partition_id,
                bypass_ids=[resource_id] if bypass else None,
                unbypass_ids=[resource_id] if not bypass else None,
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Failed to {'bypass' if bypass else 'unbypass'} Alarm.com sensor {resource_id}: {err}"
            ) from err

    bypass_schema = vol.Schema(
        {
            vol.Required(ATTR_RESOURCE_ID): cv.string,
            vol.Optional(ATTR_PARTITION_ID): cv.string,
        }
    )

    if not hass.services.has_service(DOMAIN, SERVICE_BYPASS_SENSOR):
        hass.services.async_register(DOMAIN, SERVICE_BYPASS_SENSOR, handle_bypass_service, schema=bypass_schema)

    if not hass.services.has_service(DOMAIN, SERVICE_UNBYPASS_SENSOR):
        hass.services.async_register(DOMAIN, SERVICE_UNBYPASS_SENSOR, handle_bypass_service, schema=bypass_schema)

    def _validate_own_light_entity_ids(entity_ids: list[str]) -> None:
        """Raise ServiceValidationError if any entity_id isn't one of this config entry's own light entities."""

        registry = er.async_get(hass)
        for entity_id in entity_ids:
            entry = registry.async_get(entity_id)
            if (
                entry is None
                or entry.platform != DOMAIN
                or entry.domain != "light"
                or entry.config_entry_id != config_entry.entry_id
            ):
                raise ServiceValidationError(
                    f"{entity_id} is not a light entity belonging to this Alarm.com account. "
                    "Auto-off only supports Alarm.com light entities from this config entry."
                )

    async def handle_set_auto_off(call: ServiceCall) -> None:
        """Schedule the target light(s) to turn off after a duration."""

        entity_ids = call.data[ATTR_ENTITY_ID]
        duration: timedelta = call.data[ATTR_DURATION]
        _validate_own_light_entity_ids(entity_ids)

        for entity_id in entity_ids:
            off_at = await auto_off_manager.async_set(entity_id, duration)
            LOGGER.debug("Auto-off scheduled for %s at %s", entity_id, off_at.isoformat())

    async def handle_cancel_auto_off(call: ServiceCall) -> None:
        """Cancel a pending auto-off for the target light(s)."""

        entity_ids = call.data[ATTR_ENTITY_ID]
        _validate_own_light_entity_ids(entity_ids)

        for entity_id in entity_ids:
            await auto_off_manager.async_cancel(entity_id)

    if not hass.services.has_service(DOMAIN, SERVICE_SET_AUTO_OFF):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_AUTO_OFF,
            handle_set_auto_off,
            schema=vol.Schema(
                {
                    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
                    vol.Required(ATTR_DURATION): cv.positive_time_period,
                }
            ),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_CANCEL_AUTO_OFF):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CANCEL_AUTO_OFF,
            handle_cancel_auto_off,
            schema=vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_ids}),
        )


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

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

    if config_entry.version == 2:
        LOGGER.debug("Migrating from version %s", config_entry.version)

        v3_options = {**config_entry.options}

        if not v3_options.get("use_arm_code"):
            v3_options["arm_code"] = None

        new_arm_home: list[str] = []
        if v3_options.get("force_bypass") in ["Stay Only", "Always"]:
            new_arm_home.append("bypass")
        if v3_options.get("silent_arming") in ["Stay Only", "Always"]:
            new_arm_home.append("silent")
        if v3_options.get("no_entry_delay") not in ["Stay Only", "Always"]:
            new_arm_home.append("delay")
        v3_options[CONF_ARM_HOME] = new_arm_home

        new_arm_away: list[str] = []
        if v3_options.get("force_bypass") in ["Away Only", "Always"]:
            new_arm_away.append("bypass")
        if v3_options.get("silent_arming") in ["Away Only", "Always"]:
            new_arm_away.append("silent")
        if v3_options.get("no_entry_delay") not in ["Away Only", "Always"]:
            new_arm_away.append("delay")
        v3_options[CONF_ARM_AWAY] = new_arm_away

        new_arm_night: list[str] = []
        if v3_options.get("force_bypass") == "Always":
            new_arm_night.append("bypass")
        if v3_options.get("silent_arming") == "Always":
            new_arm_night.append("silent")
        if v3_options.get("no_entry_delay") != "Always":
            new_arm_night.append("delay")
        v3_options[CONF_ARM_NIGHT] = new_arm_night

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

    if config_entry.version == 3:
        LOGGER.debug("Migrating from version %s", config_entry.version)

        v4_options: dict = {**config_entry.options}

        v4_options.pop("use_arm_code", None)
        v4_options.pop("force_bypass", None)
        v4_options.pop("silent_arming", None)
        v4_options.pop("no_entry_delay", None)

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

    if config_entry.version == 4:
        LOGGER.debug("Migrating from version %s", config_entry.version)

        v5_options: dict = {**config_entry.options}
        v5_options.pop("update_interval", None)
        v5_options.pop("ws_reconnect_timeout", None)

        hass.config_entries.async_update_entry(
            config_entry, data={**config_entry.data}, options=v5_options, version=5
        )
        LOGGER.info("Migration to version %s successful", 5)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    entry_data: AlarmEntryData = config_entry.runtime_data
    hub = entry_data.hub
    camera_session = entry_data.camera_session
    auto_off_manager = entry_data.auto_off_manager
    activity_feed_tracker = entry_data.activity_feed_tracker

    if camera_session is not None:
        await camera_session.close()

    await auto_off_manager.async_unload()
    activity_feed_tracker.async_stop()
    unload_success = await hub.close()

    # LOADED, not merely present: async_entries() includes disabled and ignored
    # entries, which have no hub and cannot serve these services. Counting them
    # keeps the services registered against the hub closed three lines above.
    remaining = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id != config_entry.entry_id and e.state is ConfigEntryState.LOADED
    ]
    if not remaining:
        for service in (
            SERVICE_BYPASS_SENSOR, SERVICE_UNBYPASS_SENSOR, SERVICE_SET_AUTO_OFF,
            SERVICE_CANCEL_AUTO_OFF, SERVICE_SET_TEMPORARY_ACCESS, SERVICE_GET_TEMPORARY_USER_SCHEDULE,
        ):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)

    return unload_success
