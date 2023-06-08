"""Const for the Alarmdotcom integration."""
from __future__ import annotations

import logging

from homeassistant.const import Platform
from pyalarmdotcomajax import const as libConst
from pyalarmdotcomajax.devices.sensor import Sensor as libSensor

INTEGRATION_NAME = "Alarm.com"
DOMAIN = "alarmdotcom"
ISSUE_URL = "https://github.com/pyalarmdotcom/alarmdotcom/issues"
STARTUP_MESSAGE = f"""
===================================================================
{DOMAIN}
This is a custom component
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
===================================================================
"""

STATE_MALFUNCTION = "Malfunction"

DEBUG_REQ_EVENT = "alarmdotcom_debug_request"

MIGRATE_MSG_ALERT = (
    "The Alarm.com integration is now configured exclusively via Home Assistant's"
    " integrations page. Please delete the Alarm.com entry from configuration.yaml."
    " Your existing settings have already been migrated."
)

KEEP_ALIVE_INTERVAL_SECONDS = 60
CONF_DEFAULT_UPDATE_INTERVAL_SECONDS = 900  # 15 minutes

LOGGER = logging.getLogger(__package__)

# #
# CONFIGURATION
# #

# Configuration
CONF_2FA_COOKIE = "2fa_cookie"
CONF_OTP = "otp"
CONF_OTP_METHOD = "otp_method"
CONF_OTP_METHODS_LIST = "otp_methods_list"

CONF_ARM_CODE = "arm_code"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_ARM_HOME = "arm_home_options"
CONF_ARM_AWAY = "arm_away_options"
CONF_ARM_NIGHT = "arm_night_options"


CONF_FORCE_BYPASS = "force_bypass"
CONF_SILENT_ARM = "silent_arming"
CONF_NO_ENTRY_DELAY = "no_entry_delay"
CONF_ARM_MODE_OPTIONS = {
    CONF_FORCE_BYPASS: "Force Bypass",
    CONF_SILENT_ARM: "Arm Silently",
    CONF_NO_ENTRY_DELAY: "No Entry Delay",
}

CONF_OPTIONS_DEFAULT = {
    CONF_ARM_CODE: "",
    CONF_ARM_HOME: [],
    CONF_ARM_AWAY: [],
    CONF_ARM_NIGHT: [],
    CONF_UPDATE_INTERVAL: CONF_DEFAULT_UPDATE_INTERVAL_SECONDS,
}

SENSOR_SUBTYPE_BLACKLIST = [
    libSensor.Subtype.MOBILE_PHONE,  # No purpose
    libSensor.Subtype.PANEL_IMAGE_SENSOR,  # No support yet
    libSensor.Subtype.FIXED_PANIC,  # Doesn't support state reporting
]

DATA_CONTROLLER = "connection"
DATA_LISTENER = "listener"

ATTRIB_BATTERY_NORMAL = "Normal"
ATTRIB_BATTERY_LOW = "Low"
ATTRIB_BATTERY_CRITICAL = "Critical"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.COVER,
    Platform.LIGHT,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.CLIMATE,
]

DEVICE_STATIC_ATTRIBUTES = [libConst.ATTR_STATE_TEXT, libConst.ATTR_MAC_ADDRESS]
