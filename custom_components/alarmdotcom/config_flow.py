"""Config flow to configure Alarmdotcom."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import voluptuous as vol

from pyalarmdotcomajax.const import ArmingOption as ADCArmingOption
from pyalarmdotcomajax.errors import AuthenticationFailed

from . import const as adci
from .controller import get_controller

log = logging.getLogger(__name__)


class ADCFlowHandler(config_entries.ConfigFlow, domain=adci.DOMAIN):  # type: ignore
    """Handle a Alarmdotcom config flow."""

    def __init__(self) -> None:
        """Initialize the Alarmdotcom flow."""
        self.adc = None
        self.config: dict = {}
        self.system_id: str | None = None
        self.sensor_data: dict | None = {}
        self._config_title: str | None = None
        self._existing_entry: config_entries.ConfigEntry | None = None
        self._imported_options = None

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
                api = await get_controller(
                    self.hass,
                    self.config[adci.CONF_USERNAME],
                    self.config[adci.CONF_PASSWORD],
                    self.config[adci.CONF_2FA_COOKIE],
                )

                self._existing_entry = await self.async_set_unique_id(
                    f"{api.provider_name}:{api.user_id}"
                )

                self._config_title = f"{api.provider_name}: {api.user_email}"

            except ConnectionError as err:
                log.error(
                    "%s: get_controller failed with CannotConnect exception: %s",
                    __name__,
                    err,
                )
                errors["base"] = "invalid_auth"
            except AuthenticationFailed as err:
                log.error(
                    "%s: get_controller failed with InvalidAuth exception: %s",
                    __name__,
                    err,
                )
                errors["base"] = "cannot_connect"

            return await self.async_step_final()

        creds_schema = vol.Schema(
            {
                vol.Required(adci.CONF_USERNAME): str,
                vol.Required(adci.CONF_PASSWORD): str,
                vol.Optional(adci.CONF_2FA_COOKIE): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=creds_schema, errors=errors, last_step=True
        )

    async def async_step_final(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create configuration entry using entered data."""

        if self._existing_entry:
            log.debug(
                "Existing config entry found. Updating entry, then aborting config"
                " flow."
            )
            self.hass.config_entries.async_update_entry(
                self._existing_entry, data=user_input
            )
            await self.hass.config_entries.async_reload(self._existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        # TODO: For non-imported flows, set options to defaults as defined in options flow handler.
        # TODO: For imported flows, validate options through schema.
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

        self.config = _convert_imported_configuration(import_config)
        self._imported_options = _convert_imported_options(import_config)

        log.debug("%s: Done reading config options. Trying to log in.", __name__)

        self._async_abort_entries_match({**self.config})

        try:
            api = await get_controller(
                self.hass,
                self.config[adci.CONF_USERNAME],
                self.config[adci.CONF_PASSWORD],
                self.config[adci.CONF_2FA_COOKIE],
            )

            self._existing_entry = await self.async_set_unique_id(
                f"{api.provider_name}:{api.user_id}"
            )

            self._config_title = f"{api.provider_name}: {api.user_email}"

        except ConnectionError as err:
            log.error(
                "%s: get_controller failed with CannotConnect exception: %s",
                __name__,
                err,
            )
            raise ConfigEntryNotReady from err
        except AuthenticationFailed as err:
            log.error(
                "%s: get_controller failed with InvalidAuth exception: %s",
                __name__,
                err,
            )
            raise ConfigEntryAuthFailed from err

        return await self.async_step_final()

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
        """Manage the options for the custom component."""
        errors: dict = {}

        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        return self.async_show_form(
            step_id="init",
            data_schema=self.schema,
            errors=errors,
            last_step=True,
        )

    async def _update_options(self) -> FlowResult:
        return self.async_create_entry(title="", data=self.options)

    @property
    def schema(self) -> vol.Schema:
        """Input schema for integration options."""
        return vol.Schema(
            {
                vol.Optional(
                    adci.CONF_ARM_CODE,
                    default=self.options.get(adci.CONF_ARM_CODE, None),
                ): str,
                vol.Required(
                    adci.CONF_FORCE_BYPASS,
                    default=self.options.get(
                        adci.CONF_FORCE_BYPASS, adci.ADCIArmingOption.NEVER.value
                    ),
                ): vol.In(
                    [
                        adci.ADCIArmingOption.NEVER.value,
                        adci.ADCIArmingOption.ALWAYS.value,
                        adci.ADCIArmingOption.STAY.value,
                        adci.ADCIArmingOption.AWAY.value,
                    ]
                ),
                vol.Required(
                    adci.CONF_NO_DELAY,
                    default=self.options.get(
                        adci.CONF_NO_DELAY, adci.ADCIArmingOption.NEVER.value
                    ),
                ): vol.In(
                    [
                        adci.ADCIArmingOption.NEVER.value,
                        adci.ADCIArmingOption.ALWAYS.value,
                        adci.ADCIArmingOption.STAY.value,
                        adci.ADCIArmingOption.AWAY.value,
                    ]
                ),
                vol.Required(
                    adci.CONF_SILENT_ARM,
                    default=self.options.get(
                        adci.CONF_SILENT_ARM, adci.ADCIArmingOption.NEVER.value
                    ),
                ): vol.In(
                    [
                        adci.ADCIArmingOption.NEVER.value,
                        adci.ADCIArmingOption.ALWAYS.value,
                        adci.ADCIArmingOption.STAY.value,
                        adci.ADCIArmingOption.AWAY.value,
                    ]
                ),
            }
        )


def _convert_imported_configuration(config: dict[str, Any]) -> Any:
    """Convert a key from the imported configuration."""

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    two_factor_cookie = config.get(adci.LEGACY_CONF_TWO_FACTOR_COOKIE)

    data: dict = {}

    data[adci.CONF_USERNAME] = username
    data[adci.CONF_PASSWORD] = password

    if two_factor_cookie:
        data[adci.CONF_2FA_COOKIE] = two_factor_cookie

    return data


def _convert_imported_options(config: dict[str, Any]) -> Any:
    """Convert a key from the imported configuration."""

    code: str | None = config.get(CONF_CODE)
    force_bypass: ADCArmingOption | None = config.get(adci.LEGACY_CONF_FORCE_BYPASS)
    no_entry_delay: ADCArmingOption | None = config.get(adci.LEGACY_CONF_NO_ENTRY_DELAY)
    silent_arming: ADCArmingOption | None = config.get(adci.LEGACY_CONF_SILENT_ARMING)

    data: dict = {}

    if code:
        data[adci.CONF_ARM_CODE] = code

    if force_bypass:
        data[adci.CONF_FORCE_BYPASS] = adci.ADCIArmingOption.from_config_yaml(
            force_bypass
        ).value

    if no_entry_delay:
        data[adci.CONF_NO_DELAY] = adci.ADCIArmingOption.from_config_yaml(
            no_entry_delay
        ).value

    if silent_arming:
        data[adci.CONF_SILENT_ARM] = adci.ADCIArmingOption.from_config_yaml(
            silent_arming
        ).value

    return data
