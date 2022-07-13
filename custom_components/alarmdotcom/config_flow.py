"""Config flow to configure Alarmdotcom."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from typing import Literal

import aiohttp
from homeassistant import config_entries
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector
from homeassistant.helpers.update_coordinator import UpdateFailed
from pyalarmdotcomajax import AuthResult as libAuthResult
from pyalarmdotcomajax.errors import AuthenticationFailed as libAuthenticationFailed
from pyalarmdotcomajax.errors import DataFetchFailed as libDataFetchFailed
import voluptuous as vol

from .alarmhub import BasicAlarmHub
from .const import CONF_2FA_COOKIE
from .const import CONF_ARM_AWAY
from .const import CONF_ARM_CODE
from .const import CONF_ARM_HOME
from .const import CONF_ARM_MODE_OPTIONS
from .const import CONF_ARM_NIGHT
from .const import CONF_OPTIONS_DEFAULT
from .const import CONF_OTP
from .const import CONF_PASSWORD
from .const import CONF_UPDATE_INTERVAL
from .const import CONF_UPDATE_INTERVAL_DEFAULT
from .const import CONF_USERNAME
from .const import DOMAIN

log = logging.getLogger(__name__)
LegacyArmingOptions = Literal["home", "away", "true", "false"]


class ADCFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore
    """Handle a Alarmdotcom config flow."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize the Alarmdotcom flow."""
        self.adc = None
        self.config: dict = {}
        self.system_id: str | None = None
        self.sensor_data: dict | None = {}
        self._config_title: str | None = None
        self._existing_entry: config_entries.ConfigEntry | None = None
        self._imported_options = None
        self._alarmhub: BasicAlarmHub | None = None

        self._force_generic_name: bool = False

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ADCOptionsFlowHandler:
        """Tell Home Assistant that this integration supports configuration options."""
        return ADCOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Gather configuration data when flow is initiated via the user interface."""
        errors = {}

        if user_input is not None:

            self.config = {
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_2FA_COOKIE: user_input.get(CONF_2FA_COOKIE),
            }

            try:
                self._alarmhub = BasicAlarmHub(self.hass)

                log.debug("Logging in to Alarm.com...")

                login_result = await self._alarmhub.async_login(
                    username=self.config[CONF_USERNAME],
                    password=self.config[CONF_PASSWORD],
                    twofactorcookie=self.config[CONF_2FA_COOKIE],
                    new_websession=True,
                )

                log.debug("Login result: %s", login_result)

                if login_result == libAuthResult.ENABLE_TWO_FACTOR:
                    return self.async_abort(reason="must_enable_2fa")

                if login_result == libAuthResult.OTP_REQUIRED:
                    log.debug("OTP code required.")
                    return await self.async_step_otp()

                if login_result == libAuthResult.SUCCESS:
                    return await self.async_step_final()

                errors["base"] = "unknown"

            except (UpdateFailed, ConfigEntryNotReady) as err:
                log.error(
                    "%s: user login failed to contact Alarm.com: %s",
                    __name__,
                    err,
                )
                errors["base"] = "cannot_connect"
            except ConfigEntryAuthFailed as err:
                log.error(
                    "%s: user login failed with InvalidAuth exception: %s",
                    __name__,
                    err,
                )
                errors["base"] = "invalid_auth"

        creds_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=creds_schema, errors=errors, last_step=False
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Gather OTP when integration configured through UI."""
        errors = {}
        if user_input is not None:

            try:

                if not isinstance(self._alarmhub, BasicAlarmHub):
                    raise ConnectionError("Failed to get ADC alarmhub.")

                await self._alarmhub.async_send_otp(user_input[CONF_OTP])

                if cookie := self._alarmhub.two_factor_cookie:
                    self.config[CONF_2FA_COOKIE] = cookie
                else:
                    raise libAuthenticationFailed(
                        "OTP submission failed. Two-factor cookie not found."
                    )

            except (ConnectionError, libDataFetchFailed) as err:
                log.error(
                    "%s: OTP submission failed with CannotConnect exception: %s",
                    __name__,
                    err,
                )
                errors["base"] = "cannot_connect"

            except libAuthenticationFailed as err:
                log.error(
                    "%s: Incorrect OTP: %s",
                    __name__,
                    err,
                )
                errors["base"] = "invalid_otp"

            else:
                return await self.async_step_final()

        creds_schema = vol.Schema(
            {
                vol.Required(CONF_OTP): str,
            }
        )

        return self.async_show_form(
            step_id="otp", data_schema=creds_schema, errors=errors, last_step=True
        )

    async def async_step_final(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create configuration entry using entered data."""

        if not isinstance(self._alarmhub, BasicAlarmHub):
            raise ConnectionError("Failed to get ADC alarmhub.")

        self._config_title = (
            "Alarm.com"
            if self._force_generic_name
            else f"{self._alarmhub.provider_name}:{self._alarmhub.user_email}"
        )

        self._existing_entry = await self.async_set_unique_id(self._config_title)

        if self._existing_entry:
            log.debug(
                "Existing config entry found. Updating entry, then aborting config"
                " flow."
            )
            self.hass.config_entries.async_update_entry(
                self._existing_entry, data=self.config
            )
            await self.hass.config_entries.async_reload(self._existing_entry.entry_id)

            return self.async_abort(reason="reauth_successful")

        options = (
            self._imported_options if self._imported_options else CONF_OPTIONS_DEFAULT
        )

        # Named async_ but doesn't require await!
        return self.async_create_entry(
            title=self._config_title, data=self.config, options=options
        )

    # #
    # Import from configuration.yaml
    # #

    # https://github.com/home-assistant/core/blob/56bda80e0a799404001efe309f52ea1f8a20f479/homeassistant/components/version/config_flow.py
    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""

        log.debug("%s: Importing configuration data from configuration.yaml.", __name__)

        self.config = _convert_v_0_1_imported_configuration(import_config)
        self._imported_options = _convert_v_0_1_imported_options(import_config)

        log.debug("%s: Done reading config options. Logging in...", __name__)

        self._async_abort_entries_match({**self.config})

        try:
            self._alarmhub = BasicAlarmHub(self.hass)

            login_result = await self._alarmhub.async_login(
                username=self.config[CONF_USERNAME],
                password=self.config[CONF_PASSWORD],
                twofactorcookie=self.config[CONF_2FA_COOKIE],
                new_websession=True,
            )

            log.debug("Login result: %s", login_result)

            # If provider requires 2FA, create config entry anyway. Will fail on update and prompt for reauth.
            if login_result != libAuthResult.SUCCESS:
                self._force_generic_name = True

            return await self.async_step_final()

        except (
            ConfigEntryAuthFailed,
            UpdateFailed,
            ConfigEntryNotReady,
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ) as err:
            log.error(
                "%s: Failed to log in when migrating from configuration.yaml: %s",
                __name__,
                err,
            )
            raise

    # #
    # Reauthentication Steps
    # #

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        log.debug("Reauthenticating.")
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()


class ADCOptionsFlowHandler(config_entries.OptionsFlow):  # type: ignore
    """Handle option configuration via Integrations page."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """First screen for configuration options. Sets arming code."""
        errors: dict = {}

        if user_input is not None:
            if user_input.get(CONF_ARM_CODE) == "CLEAR!":
                user_input[CONF_ARM_CODE] = ""
            self.options.update(user_input)
            return await self.async_step_modes()

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ARM_CODE,
                    default=""
                    if not (arm_code_raw := self.options.get(CONF_ARM_CODE))
                    else arm_code_raw,
                ): selector.selector({"text": {"type": "password"}}),
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=self.options.get(
                        CONF_UPDATE_INTERVAL, CONF_UPDATE_INTERVAL_DEFAULT
                    ),
                ): selector.selector(
                    {
                        "number": {
                            "mode": "box",
                            CONF_UNIT_OF_MEASUREMENT: "seconds",
                        }
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            last_step=False,
        )

    async def async_step_modes(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """First screen for configuration options. Sets arming mode profiles."""
        errors: dict = {}

        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ARM_HOME,
                    default=self.options.get(
                        CONF_ARM_HOME, CONF_OPTIONS_DEFAULT[CONF_ARM_HOME]
                    ),
                ): cv.multi_select(CONF_ARM_MODE_OPTIONS),
                vol.Required(
                    CONF_ARM_AWAY,
                    default=self.options.get(
                        CONF_ARM_AWAY, CONF_OPTIONS_DEFAULT[CONF_ARM_AWAY]
                    ),
                ): cv.multi_select(CONF_ARM_MODE_OPTIONS),
                vol.Required(
                    CONF_ARM_NIGHT,
                    default=self.options.get(
                        CONF_ARM_NIGHT, CONF_OPTIONS_DEFAULT[CONF_ARM_NIGHT]
                    ),
                ): cv.multi_select(CONF_ARM_MODE_OPTIONS),
            }
        )

        return self.async_show_form(
            step_id="modes",
            data_schema=schema,
            errors=errors,
            last_step=True,
        )


def _convert_v_0_1_imported_configuration(config: dict[str, Any | None]) -> Any:
    """Convert a key from the imported configuration."""

    username = config.get("username")
    password = config.get("password")
    two_factor_cookie = config.get("two_factor_cookie")

    data: dict = {}

    data[CONF_USERNAME] = username
    data[CONF_PASSWORD] = password
    data[CONF_2FA_COOKIE] = two_factor_cookie if two_factor_cookie else None

    return data


def _convert_v_0_1_imported_options(config: dict[str, Any]) -> Any:
    """Convert a key from the imported configuration."""

    code: str | int | None = config.get("code")
    force_bypass: LegacyArmingOptions | None = config.get("force_bypass")
    no_entry_delay: LegacyArmingOptions | None = config.get("no_entry_delay")
    silent_arming: LegacyArmingOptions | None = config.get("silent_arming")

    data: dict = {}

    if code:
        data[CONF_ARM_CODE] = str(code)

    # Populate Arm Home
    new_arm_home = []

    if force_bypass in ["home", "true"]:
        new_arm_home.append("bypass")
    if silent_arming in ["home", "true"]:
        new_arm_home.append("silent")
    if no_entry_delay not in ["home", "true"]:
        new_arm_home.append("delay")

    data[CONF_ARM_HOME] = new_arm_home

    # Populate Arm Away
    new_arm_away = []

    if force_bypass in ["away", "true"]:
        new_arm_away.append("bypass")
    if silent_arming in ["away", "true"]:
        new_arm_away.append("silent")
    if no_entry_delay not in ["away", "true"]:
        new_arm_away.append("delay")

    data[CONF_ARM_AWAY] = new_arm_away

    # Populate Arm Night
    new_arm_night = []

    if force_bypass == "true":
        new_arm_night.append("bypass")
    if silent_arming == "true":
        new_arm_night.append("silent")
    if no_entry_delay != "true":
        new_arm_night.append("delay")

    data[CONF_ARM_NIGHT] = new_arm_night

    return data
