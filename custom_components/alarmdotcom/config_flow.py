"""Config flow to configure Alarmdotcom."""

import logging
from typing import TYPE_CHECKING, Any, Literal

import aiohttp
import async_timeout
import pyalarmdotcomajax as pyadc
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_ARM_AWAY,
    CONF_ARM_CODE,
    CONF_ARM_HOME,
    CONF_ARM_MODE_OPTIONS,
    CONF_ARM_NIGHT,
    CONF_MFA_TOKEN,
    CONF_OPTIONS_DEFAULT,
    CONF_OTP,
    CONF_OTP_METHOD,
    CONF_OTP_METHODS_LIST,
    CONF_REMOVE_ARM_CODE,
    DOMAIN,
)

if TYPE_CHECKING:
    from .hub import AlarmHub

LOGGER = logging.getLogger(__name__)
LegacyArmingOptions = Literal["home", "away", "true", "false"]


class ADCFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Alarmdotcom config flow."""

    VERSION = 4

    def __init__(self) -> None:
        """Initialize the Alarmdotcom flow."""
        self.config: dict = {}
        self.system_id: str | None = None
        self.sensor_data: dict | None = {}
        self._config_title: str | None = None
        self._controller: AlarmHub
        self._existing_entry: config_entries.ConfigEntry | None = None

        self._otp_options: pyadc.OtpRequired | None = None

        self._force_generic_name: bool = False

        self.otp_method: pyadc.OtpType | None = None

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "ADCOptionsFlowHandler":
        """Tell Home Assistant that this integration supports configuration options."""

        return ADCOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Gather configuration data when flow is initiated via the user interface."""
        errors = {}

        if user_input is not None:
            self.config = {
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_MFA_TOKEN: user_input.get(CONF_MFA_TOKEN),
            }

            LOGGER.debug("Logging in to Alarm.com...")

            self.bridge = pyadc.AlarmBridge(
                username=self.config[CONF_USERNAME],
                password=self.config[CONF_PASSWORD],
                mfa_token=self.config[CONF_MFA_TOKEN],
            )

            async with async_timeout.timeout(60):
                try:
                    await self.bridge.login()
                except pyadc.OtpRequired as exc:
                    LOGGER.debug("OTP code required.")
                    self._otp_options = exc
                    return await self.async_step_otp_select_method()
                except pyadc.MustConfigureMfa:
                    return self.async_abort(reason="must_enable_2fa")
                except (
                    TimeoutError,
                    aiohttp.ClientError,
                    pyadc.UnexpectedResponse,
                    pyadc.NotAuthorized,
                ):
                    LOGGER.exception(
                        "%s: user login failed to contact Alarm.com.",
                        __name__,
                    )
                    errors["base"] = "cannot_connect"
                except pyadc.AuthenticationFailed:
                    LOGGER.exception(
                        "%s: user login failed with AuthenticationFailed exception.",
                        __name__,
                    )
                    errors["base"] = "invalid_auth"
                except Exception:
                    LOGGER.exception("Got error while initializing Alarm.com.")
                    errors["base"] = "unknown"
                else:
                    return await self.async_step_final()

        creds_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.TEXT, autocomplete="username"
                    )
                ),
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD, autocomplete="current-password"
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=creds_schema, errors=errors, last_step=False
        )

    async def async_step_otp_select_method(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select OTP method when integration configured through UI."""

        if not self._otp_options:
            raise ConfigEntryError("No OTP options found.")

        errors = {}

        if user_input is not None:
            self.otp_method = pyadc.OtpType(
                {otp_type.name: otp_type.value for otp_type in pyadc.OtpType}.get(
                    user_input[CONF_OTP_METHOD]
                )
            )
            if self.otp_method in (pyadc.OtpType.email, pyadc.OtpType.sms):
                # Ask Alarm.com to send OTP if selected method is EMAIL or SMS.
                LOGGER.debug(
                    "Requesting One-Time Password via %s...", self.otp_method.name
                )
                await self.bridge.auth_controller.request_otp(self.otp_method)

            return await self.async_step_otp_submit()

        try:
            # Get list of enabled OTP methods.
            if len(self._otp_options.enabled_2fa_methods) == 1:
                # If only one OTP method is enabled, use it without prompting user.
                self.otp_method = self._otp_options.enabled_2fa_methods[0]
                LOGGER.debug("Using %s for One-Time Password.", self.otp_method.name)
                return await self.async_step_otp_submit()

        except (TimeoutError, aiohttp.ClientError, pyadc.UnexpectedResponse):
            LOGGER.exception(
                "%s: OTP submission failed connection exception.",
                __name__,
            )
            errors["base"] = "cannot_connect"

        otp_method_schema = vol.Schema(
            {
                vol.Required(
                    CONF_OTP_METHOD,
                    default=self._otp_options.enabled_2fa_methods[0].name,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            otp_type.name
                            for otp_type in self._otp_options.enabled_2fa_methods
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_OTP_METHODS_LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="otp_select_method",
            data_schema=otp_method_schema,
            errors=errors,
            last_step=False,
        )

    async def async_step_otp_submit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Gather OTP when integration configured through UI."""
        errors = {}
        if user_input is not None:
            if not self.otp_method:
                raise AttributeError("OTP method not selected.")

            try:
                mfa_cookie = await self.bridge.auth_controller.submit_otp(
                    method=self.otp_method,
                    code=user_input[CONF_OTP],
                    device_name=f"Home Assistant ({self.hass.config.location_name})",
                )

                if mfa_cookie:
                    self.config[CONF_MFA_TOKEN] = mfa_cookie
                else:
                    raise pyadc.AuthenticationFailed(
                        "OTP submission failed. Two-factor cookie not found."
                    )

            except (
                TimeoutError,
                aiohttp.ClientError,
                pyadc.UnexpectedResponse,
                pyadc.NotAuthorized,
            ):
                LOGGER.exception(
                    "%s: OTP submission failed with CannotConnect exception.",
                    __name__,
                )
                errors["base"] = "cannot_connect"

            except pyadc.AuthenticationFailed:
                LOGGER.exception(
                    "%s: Incorrect OTP code entered.",
                    __name__,
                )
                errors["base"] = "invalid_otp"

            else:
                return await self.async_step_final()

        creds_schema = vol.Schema(
            {
                vol.Required(CONF_OTP): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.TEXT, autocomplete="one-time-code"
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="otp_submit",
            data_schema=creds_schema,
            errors=errors,
            last_step=True,
        )

    async def async_step_final(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create configuration entry using entered data."""

        # Fetch full state as a lazy way to get active_system_name. (Controller must be initialized.)
        await self.bridge.fetch_full_state()

        self._config_title = f"{self.bridge.active_system.name} ({self.bridge.auth_controller.dealer}):{self.bridge.auth_controller.user_email}"

        if self._existing_entry:
            LOGGER.debug(
                "Existing config entry found. Updating entry, then aborting config flow."
            )
            self.hass.config_entries.async_update_entry(
                self._existing_entry, data=self.config
            )
            await self.hass.config_entries.async_reload(self._existing_entry.entry_id)

            return self.async_abort(reason="reauth_successful")

        # Named async_ but doesn't require await!
        return self.async_create_entry(
            title=self._config_title, data=self.config, options=CONF_OPTIONS_DEFAULT
        )

    # #
    # Reauthentication Steps
    # #

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        LOGGER.debug("Reauthenticating.")
        self._existing_entry = await self.async_set_unique_id(self._config_title)
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()


class ADCOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle option configuration via Integrations page."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First screen for configuration options. Sets arming code."""
        errors: dict = {}

        if user_input is not None:
            if user_input[CONF_REMOVE_ARM_CODE]:
                user_input[CONF_ARM_CODE] = ""
            self.options.update(user_input)
            self.options.pop(CONF_REMOVE_ARM_CODE, None)  # Remove the helper key
            return await self.async_step_modes()

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ARM_CODE,
                    default=(
                        ""
                        if not (arm_code_raw := self.options.get(CONF_ARM_CODE))
                        else arm_code_raw
                    ),
                ): selector.selector({"text": {"type": "password"}}),
                vol.Optional(
                    CONF_REMOVE_ARM_CODE,
                    default=False,
                ): selector.selector({"boolean": {}}),
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
    ) -> ConfigFlowResult:
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
