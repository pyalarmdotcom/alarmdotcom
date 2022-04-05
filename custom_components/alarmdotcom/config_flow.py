"""Config flow to configure Alarmdotcom."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from typing import Literal

import aiohttp
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import UpdateFailed
from pyalarmdotcomajax.const import AuthResult
from pyalarmdotcomajax.errors import AuthenticationFailed
from pyalarmdotcomajax.errors import DataFetchFailed
import voluptuous as vol

from . import const as adci
from .controller import ADCIController

log = logging.getLogger(__name__)
LegacyArmingOptions = Literal["home", "away", "true", "false"]


class ADCFlowHandler(config_entries.ConfigFlow, domain=adci.DOMAIN):  # type: ignore
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
        self._controller: ADCIController | None = None

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
                adci.CONF_USERNAME: user_input[adci.CONF_USERNAME],
                adci.CONF_PASSWORD: user_input[adci.CONF_PASSWORD],
                adci.CONF_2FA_COOKIE: user_input.get(adci.CONF_2FA_COOKIE),
            }

            try:
                self._controller = ADCIController(self.hass)

                log.debug("Logging in to Alarm.com...")

                login_result = await self._controller.async_login(
                    username=self.config[adci.CONF_USERNAME],
                    password=self.config[adci.CONF_PASSWORD],
                    twofactorcookie=self.config[adci.CONF_2FA_COOKIE],
                )

                log.debug("Login result: %s", login_result)

                if login_result == AuthResult.ENABLE_TWO_FACTOR:
                    return self.async_abort(reason="must_enable_2fa")

                elif login_result == AuthResult.OTP_REQUIRED:
                    log.debug("OTP code required.")
                    return await self.async_step_otp()

                elif login_result == AuthResult.SUCCESS:
                    return await self.async_step_final()

                else:
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
                vol.Required(adci.CONF_USERNAME): str,
                vol.Required(adci.CONF_PASSWORD): str,
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

                if not isinstance(self._controller, ADCIController):
                    raise ConnectionError("Failed to get ADC controller.")

                await self._controller.async_send_otp(user_input[adci.CONF_OTP])

                if cookie := self._controller.two_factor_cookie:
                    self.config[adci.CONF_2FA_COOKIE] = cookie
                else:
                    raise AuthenticationFailed(
                        "OTP submission failed. Two-factor cookie not found."
                    )

            except (ConnectionError, DataFetchFailed) as err:
                log.error(
                    "%s: OTP submission failed with CannotConnect exception: %s",
                    __name__,
                    err,
                )
                errors["base"] = "cannot_connect"

            except AuthenticationFailed as err:
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
                vol.Required(adci.CONF_OTP): str,
            }
        )

        return self.async_show_form(
            step_id="otp", data_schema=creds_schema, errors=errors, last_step=True
        )

    async def async_step_final(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create configuration entry using entered data."""

        if not isinstance(self._controller, ADCIController):
            raise ConnectionError("Failed to get ADC controller.")

        self._config_title = (
            "Alarm.com"
            if self._force_generic_name
            else f"{self._controller.provider_name}:{self._controller.user_email}"
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

        # TODO: For non-imported flows, set options to defaults as defined in options flow handler.
        # TODO: For imported flows, validate options through schema.

        # Named async_ but doesn't require await!
        return self.async_create_entry(
            title=self._config_title, data=self.config, options=self._imported_options
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
            self._controller = ADCIController(self.hass)

            login_result = await self._controller.async_login(
                username=self.config[adci.CONF_USERNAME],
                password=self.config[adci.CONF_PASSWORD],
                twofactorcookie=self.config[adci.CONF_2FA_COOKIE],
            )

            log.debug("Login result: %s", login_result)

            # If provider requires 2FA, create config entry anyway. Will fail on update and prompt for reauth.
            if login_result != AuthResult.SUCCESS:
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
            if user_input.get(adci.CONF_ARM_CODE) == "CLEAR!":
                user_input[adci.CONF_ARM_CODE] = ""
            self.options.update(user_input)
            return await self.async_step_modes()

        schema = vol.Schema(
            {
                vol.Optional(
                    adci.CONF_ARM_CODE,
                    default=""
                    if not (arm_code_raw := self.options.get(adci.CONF_ARM_CODE))
                    else arm_code_raw,
                ): cv.string,
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
            if user_input.get(adci.CONF_ARM_CODE) == "CLEAR!":
                user_input[adci.CONF_ARM_CODE] = ""
            self.options.update(user_input)
            return await self.async_step_polling()

        schema = vol.Schema(
            {
                vol.Required(
                    adci.CONF_ARM_HOME,
                    default=self.options.get(
                        adci.CONF_ARM_HOME, adci.CONF_ARM_MODE_OPTIONS_DEFAULT
                    ),
                ): cv.multi_select(adci.CONF_ARM_MODE_OPTIONS),
                vol.Required(
                    adci.CONF_ARM_AWAY,
                    default=self.options.get(
                        adci.CONF_ARM_AWAY, adci.CONF_ARM_MODE_OPTIONS_DEFAULT
                    ),
                ): cv.multi_select(adci.CONF_ARM_MODE_OPTIONS),
                vol.Required(
                    adci.CONF_ARM_NIGHT,
                    default=self.options.get(
                        adci.CONF_ARM_NIGHT, adci.CONF_ARM_MODE_OPTIONS_DEFAULT
                    ),
                ): cv.multi_select(adci.CONF_ARM_MODE_OPTIONS),
            }
        )

        return self.async_show_form(
            step_id="modes",
            data_schema=schema,
            errors=errors,
            last_step=False,
        )

    async def async_step_polling(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """First screen for configuration options. Sets update interval."""
        errors: dict = {}

        # TODO: Update interval will not take effect until HA reboots. We need to either force reboot message or find a way around this, maybe updating the coordinator directly.

        if user_input is not None:
            if user_input.get(adci.CONF_ARM_CODE) == "CLEAR!":
                user_input[adci.CONF_ARM_CODE] = ""
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        schema = vol.Schema(
            {
                vol.Required(
                    adci.CONF_UPDATE_INTERVAL,
                    default=self.options.get(
                        adci.CONF_UPDATE_INTERVAL, adci.CONF_UPDATE_INTERVAL_DEFAULT
                    ),
                ): cv.positive_int,
            }
        )

        return self.async_show_form(
            step_id="polling",
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

    data[adci.CONF_USERNAME] = username
    data[adci.CONF_PASSWORD] = password
    data[adci.CONF_2FA_COOKIE] = two_factor_cookie if two_factor_cookie else None

    return data


def _convert_v_0_1_imported_options(config: dict[str, Any]) -> Any:
    """Convert a key from the imported configuration."""

    code: str | int | None = config.get("code")
    force_bypass: LegacyArmingOptions | None = config.get("force_bypass")
    no_entry_delay: LegacyArmingOptions | None = config.get("no_entry_delay")
    silent_arming: LegacyArmingOptions | None = config.get("silent_arming")

    data: dict = {}

    if code:
        data[adci.CONF_ARM_CODE] = str(code)

    # Populate Arm Home
    new_arm_home = []

    if force_bypass in ["home", "true"]:
        new_arm_home.append("bypass")
    if silent_arming in ["home", "true"]:
        new_arm_home.append("silent")
    if no_entry_delay not in ["home", "true"]:
        new_arm_home.append("delay")

    data[adci.CONF_ARM_HOME] = new_arm_home

    # Populate Arm Away
    new_arm_away = []

    if force_bypass in ["away", "true"]:
        new_arm_away.append("bypass")
    if silent_arming in ["away", "true"]:
        new_arm_away.append("silent")
    if no_entry_delay not in ["away", "true"]:
        new_arm_away.append("delay")

    data[adci.CONF_ARM_AWAY] = new_arm_away

    # Populate Arm Night
    new_arm_night = []

    if force_bypass == "true":
        new_arm_night.append("bypass")
    if silent_arming == "true":
        new_arm_night.append("silent")
    if no_entry_delay != "true":
        new_arm_night.append("delay")

    data[adci.CONF_ARM_NIGHT] = new_arm_night

    return data
