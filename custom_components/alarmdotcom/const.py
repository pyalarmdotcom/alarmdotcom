"""Const for the Alarmdotcom integration."""

import logging

from homeassistant.const import Platform

INTEGRATION_NAME = "Alarm.com"
DOMAIN = "alarmdotcom"
ISSUE_URL = "https://github.com/ibasebcast/ha-alarmdotcom/issues"
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

SERVICE_BYPASS_SENSOR = "bypass_sensor"
SERVICE_UNBYPASS_SENSOR = "unbypass_sensor"
SERVICE_SET_AUTO_OFF = "set_auto_off"
SERVICE_CANCEL_AUTO_OFF = "cancel_auto_off"
ATTR_RESOURCE_ID = "resource_id"
ATTR_PARTITION_ID = "partition_id"
ATTR_DURATION = "duration"


MIGRATE_MSG_ALERT = (
    "The Alarm.com integration is now configured exclusively via Home Assistant's"
    " integrations page. Please delete the Alarm.com entry from configuration.yaml."
    " Your existing settings have already been migrated."
)

LOGGER = logging.getLogger(__package__)

# #
# CONFIGURATION
# #

# Configuration
CONF_MFA_TOKEN = "2fa_cookie"  # noqa: S105
CONF_OTP = "otp"
CONF_OTP_METHOD = "otp_method"
CONF_OTP_METHODS_LIST = "otp_methods_list"

CONF_ARM_CODE = "arm_code"
CONF_REMOVE_ARM_CODE = "remove_arm_code"
CONF_ARM_HOME = "arm_home_options"
CONF_ARM_AWAY = "arm_away_options"
CONF_ARM_NIGHT = "arm_night_options"


CONF_FORCE_BYPASS = "force_bypass"
CONF_SILENT_ARM = "silent_arming"
CONF_NO_ENTRY_DELAY = "no_entry_delay"

# Polling intervals - both are user-configurable via the options flow
# (see config_flow.py's ADCOptionsFlowHandler.async_step_polling), each
# with its own reasonable min/max bounds enforced there. Values here are
# just the fallback defaults used before a user has ever set an option.
CONF_ACTIVITY_POLL_INTERVAL = "activity_poll_interval"  # seconds
CONF_FULL_STATE_POLL_INTERVAL = "full_state_poll_interval"  # minutes
# How often each camera re-fetches its WebRTC stream tokens. Alarm.com does
# not document the token lifetime; 30 minutes is the value that was hardcoded
# before this became an option (#93).
CONF_CAMERA_TOKEN_REFRESH_INTERVAL = "camera_token_refresh_interval"  # minutes  # noqa: S105
CONF_CAMERA_STREAM_TRANSPORT = "camera_stream_transport"
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
    CONF_ACTIVITY_POLL_INTERVAL: 15,
    CONF_FULL_STATE_POLL_INTERVAL: 5,
    CONF_CAMERA_TOKEN_REFRESH_INTERVAL: 30,
    CONF_CAMERA_STREAM_TRANSPORT: "endToEnd",
}


ATTRIB_BATTERY_NORMAL = "Normal"
ATTRIB_BATTERY_LOW = "Low"
ATTRIB_BATTERY_CRITICAL = "Critical"

ATTRIB_MANUFACTURER = "Alarm.com"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.LOCK,
    Platform.COVER,
    Platform.LIGHT,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.VALVE,
    Platform.CAMERA,
    Platform.EVENT,
]

# #
# CAMERA
# #

CONF_CAMERA_MFA_CODE = "mfa_code"
CONF_CAMERA_MFA_COOKIE = "mfa_cookie"

# Central Scene key attributes follow Z-Wave JS naming. Scene 1 is the up/on
# paddle and scene 2 the down/off paddle on supported switches.
EVENT_SCENE = "alarmdotcom_scene"
SCENE_ACTIONS = ("KeyPressed", "KeyReleased", "KeyHeldDown", "KeyPressed2x", "KeyPressed3x", "KeyPressed4x", "KeyPressed5x")
