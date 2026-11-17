"""Authentication models."""

from dataclasses import dataclass, field
from enum import Enum

from _pyalarmdotcomajax.models.base import (
    AdcResource,
    AdcResourceAttributes,
    ResourceType,
)
from mashumaro import field_options


class OtpType(Enum):
    """Alarm.com two factor authentication type."""

    # https://www.alarm.com/web/system/assets/customer-ember/enums/TwoFactorAuthenticationType.js
    # Keep these lowercase. Strings.json in Home Assistant requires lowercase values.

    disabled = 0
    app = 1
    sms = 2
    email = 4


@dataclass
class SmsMobileNumber(AdcResourceAttributes):
    """Attributes for a user's SMS mobile number."""

    mobile_number: str = ""
    country: str = ""
    cell_provider: str = ""


@dataclass(kw_only=True)
class TwoFactorAuthenticationAttributes(AdcResourceAttributes):
    """Attributes for a user's two factor authentication options."""

    sms_mobile_number: SmsMobileNumber | None
    current_device_name: str | None = field(default=None)
    selected_type_of_2fa: int | None = field(metadata=field_options(alias="selected_type_of2_fa"), default=None)
    enabled_two_factor_types: int | None = field(default=None)
    valid2fa_permissions: list[int] = field(
        metadata=field_options(alias="valid2_fa_permissions"), default_factory=list
    )
    show_suggested_setup: bool = field(default=False)
    can_skip_suggested_setup: bool | None = field(default=None)
    is_current_device_trusted: bool = field(default=False)
    can_reset_2fa: bool = field(metadata=field_options(alias="can_reset2_fa"), default=False)
    email: str = ""

    @property
    def is_2fa_enabled(self) -> bool:
        """Return whether 2FA is enabled."""
        return self.enabled_two_factor_types > 0 if self.enabled_two_factor_types is not None else False


@dataclass
class TwoFactorAuthentication(AdcResource[TwoFactorAuthenticationAttributes]):
    """Object representing a user's two factor authentication options."""

    resource_type = ResourceType.TWO_FACTOR
    attributes_type = TwoFactorAuthenticationAttributes
