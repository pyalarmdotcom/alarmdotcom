"""Exceptions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import phonenumbers

if TYPE_CHECKING:
    from _pyalarmdotcomajax.models.auth import OtpType


class AlarmdotcomException(Exception):
    """Base exception for pyalarmdotcomajax."""


#
# DEVICE EXCEPTIONS
#


class DeviceException(AlarmdotcomException):
    """Base Alarm.com device exception."""


class UnknownDevice(DeviceException):
    """pyalarmdotcomajax did not recognize the device ID."""

    def __init__(self, device_id: str) -> None:
        """Initialize the exception."""
        super().__init__(f"Unknown device ID '{device_id}'.")


class UnsupportedOperation(DeviceException):
    """Device does not support requested action."""

    def __init__(self, message: str) -> None:
        """Initialize the exception."""
        super().__init__(f"Unsupported operation: {message}")


#
# AUTHENTICATION EXCEPTIONS
#


class AuthenticationException(AlarmdotcomException):
    """Base exception for pyalarmdotcomajax authentication and connectivity failures."""


class AuthenticationFailed(AuthenticationException):
    """Raised when the server rejects a user's login credentials."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the exception."""
        super().__init__(*args)

        self.can_autocorrect = kwargs.pop("can_autocorrect", False)


class OtpRequired(AuthenticationException):
    """Raised during login if a user had two-factor authentication enabled."""

    def __init__(
        self,
        enabled_2fa_methods: list[OtpType],
        email: str | None = None,
        sms_number: str | None = None,
        sms_country_code: str | None = None,
    ) -> None:
        """Initialize the exception."""
        super().__init__()

        self.enabled_2fa_methods = enabled_2fa_methods
        self.email = email
        self.sms_number = sms_number
        self.sms_country_code = sms_country_code

        self.formatted_sms_number = None
        if sms_number and sms_country_code:
            parsed_number = phonenumbers.parse(f"+{sms_country_code}{sms_number}")
            self.formatted_sms_number = phonenumbers.format_number(
                parsed_number, phonenumbers.PhoneNumberFormat.NATIONAL
            )


class MustConfigureMfa(AuthenticationException):
    """Raised during login if the user gets the Alarm.com nag screen to setup 2 factor authentication."""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__(
            "Alarm.com requires that two-factor authentication be set up on your account. Please log in to"
            " Alarm.com and set up two-factor authentication."
        )


class NotAuthorized(AuthenticationException):
    """Raised when the user does not have permission to perform requested action."""


#
# MISC EXCEPTIONS
#


class MiscException(AlarmdotcomException):
    """Base Alarm.com misc exception."""


class SessionExpired(MiscException):
    """Raised when the user's session has timed out and needs to be re-established."""


class ServiceUnavailable(MiscException):
    """Raised when multiple requests to the server have failed."""


class NotInitialized(MiscException):
    """Not initialized."""


class UnexpectedResponse(MiscException):
    """Successfully received server response, but format is not as expected."""
