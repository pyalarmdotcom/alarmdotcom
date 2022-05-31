"""Alarmdotcom exceptions."""
from homeassistant.exceptions import HomeAssistantError


class Require2FA(HomeAssistantError):  # type: ignore
    """Error to indicate we require 2FA."""


class CannotConnect(HomeAssistantError):  # type: ignore
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):  # type: ignore
    """Error to indicate there is invalid auth."""


class UnexpectedDataFormat(HomeAssistantError):  # type: ignore
    """Error to indicate there is invalid auth."""


class PartialInitialization(HomeAssistantError):  # type: ignore
    """Error for AlarmHub to indicate that integration has not yet been set up."""
