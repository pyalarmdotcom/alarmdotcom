"""Config flow to configure Alarmdotcom."""
import logging
from re import M

import voluptuous as vol

from typing import Any

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession,
)

from pyalarmdotcomajax import Alarmdotcom, AlarmdotcomADT, AlarmdotcomProtection1

from .const import DOMAIN
from .util import map_adc_provider

_LOGGER = logging.getLogger(__name__)

STEP_OPTIONS_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("force_bypass", default=False): bool,
        vol.Required("no_entry_delay", default=False): bool,
        vol.Required("silent_arming", default=False): bool,
        vol.Optional("arm_code"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    adc_class = map_adc_provider(data["provider"])

    alarm = adc_class(
        username=data["username"],
        password=data["password"],
        websession=async_get_clientsession(hass),
        forcebypass=False,
        noentrydelay=False,
        silentarming=False,
        twofactorcookie=data["two_factor"],
    )
    response = await alarm.async_login()

    # ADC python library needs mod to tell us whether error is due to bad creds or something else
    # so that we know whether to raise CannotConnect or InvalidAuth
    if response is False:
        raise CannotConnect

    return {"systemid": alarm.systemid}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Alarmdotcom config flow."""

    def __init__(self):
        """Initialize the Alarmdotcom flow."""
        self.adc = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""

        errors = {}
        if user_input is not None:
            try:
                response = await validate_input(self.hass, user_input)
                user_input["systemid"] = response["systemid"]
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            # except Require2FA:
            #     return await self.async_step_2fa()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input["system_name"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Optional("two_factor"): str,
                    vol.Required("provider", default="Other"): vol.All(
                        str, vol.In(["ADT", "Protection1", "Other"])
                    ),
                    vol.Required(
                        "system_name", default=f"{self.hass.config.location_name} Alarm"
                    ): str,
                }
            ),
            errors=errors,
        )

    # async def async_step_2fa(self, user_input=None):
    #     """Handle 2FA step."""
    #     if user_input is not None:
    #         pin = user_input.get(CONF_PIN)
    #         if await self.hass.async_add_executor_job(
    #             self.blink.login_handler.send_auth_key, self.blink, pin
    #         ):
    #             return await self.async_step_user(user_input=self.data)

    #     return self.async_show_form(
    #         step_id="2fa",
    #         data_schema=vol.Schema(
    #             {vol.Optional("pin"): vol.All(str, vol.Length(min=1))}
    #         ),
    #     )

    async def async_step_import(self, import_data):
        """Import blink config from configuration.yaml."""
        return await self.async_step_user(import_data)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init", data_schema=STEP_OPTIONS_DATA_SCHEMA
        )

    async def async_step_import(self, import_data):
        """Import blink config from configuration.yaml."""
        return await self.async_step_init(import_data)


class Require2FA(exceptions.HomeAssistantError):
    """Error to indicate we require 2FA."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""