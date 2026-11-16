"""Module containing dataclasses for identity-related objects."""

import logging
from dataclasses import dataclass, field

from _pyalarmdotcomajax.models.base import (
    AdcResource,
    AdcResourceAttributes,
    ResourceType,
)
from _pyalarmdotcomajax.util import get_related_entity_id_by_key
from mashumaro import field_options

#
# API IDENTITY RESPONSE
#
log = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ApplicationSessionProperties(AdcResourceAttributes):
    """A class representing application session properties."""

    # fmt: off
    should_timeout: bool = field(metadata={"description": "Specifies if the session should timeout"})
    keep_alive_url: str | None= field(metadata={"description": "URL used for keep-alive requests"}, default=None)
    enable_keep_alive: bool = field(metadata={"description": "Indicates whether keep-alive requests are enabled"})
    logout_timeout_ms: int = field(metadata={"description": "Timeout duration for logout in milliseconds"}, default=300000) # 5 minutes
    inactivity_warning_timeout_ms: int | None = field(
        metadata={
            "description": "Timeout duration for inactivity warning in milliseconds"
        }, default=None
    )
    # fmt: on


@dataclass(kw_only=True)
class IdentityAttributes(AdcResourceAttributes):
    """Attributes of a raw identity response."""

    # fmt: off
    timezone: str | None = field(default=None)
    preferred_timezone: str = field(default="UTC")
    application_session_properties: ApplicationSessionProperties
    localize_temp_units_to_celsius: bool = field(default=False)
    has_trouble_conditions_service: bool = field(default=True)
    # fmt: on


@dataclass
class Identity(AdcResource[IdentityAttributes]):
    """Identity resource."""

    resource_type = ResourceType.IDENTITY
    attributes_type = IdentityAttributes

    @property
    def keep_alive_url(self) -> str | None:
        """URL for keep-alive requests, if keep alive is enabled."""
        return (
            self.attributes.application_session_properties.keep_alive_url
            if self.attributes.application_session_properties.enable_keep_alive
            else None
        )

    @property
    def use_celsius(self) -> bool | None:
        """Whether the user uses celsius or fahrenheit."""
        return self.attributes.localize_temp_units_to_celsius or None

    @property
    def selected_system(self) -> str | None:
        """The ID of the selected system."""

        return get_related_entity_id_by_key(self.api_resource, "selected_system")

    @property
    def dealer_id(self) -> str | None:
        """The ID of the Alarm.com reseller / dealer."""

        # return self.api_resource.relationships.get("dealer").data.id

        return get_related_entity_id_by_key(self.api_resource, "dealer")


#
# API USER PROFILE RESPONSE
#


@dataclass
class ProfileAttributes(AdcResourceAttributes):
    """A class representing a user profile inclusion list entry."""

    email: str = field(metadata=field_options(alias="login_email_address"))


@dataclass
class Profile(AdcResource[ProfileAttributes]):
    """Identity resource."""

    resource_type = ResourceType.PROFILE
    attributes_type = ProfileAttributes


#
# API DEALER RESPONSE
#


@dataclass
class DealerAttributes(AdcResourceAttributes):
    """A class representing a user profile inclusion list entry."""

    name: str


@dataclass
class Dealer(AdcResource[DealerAttributes]):
    """Identity resource."""

    resource_type = ResourceType.DEALER
    attributes_type = DealerAttributes


#
# API AVAILABLE SYSTEM RESPONSE
#


@dataclass
class AvailableSystemAttributes(AdcResourceAttributes):
    """Attributes for available systems."""

    name: str
    is_selected: bool


@dataclass
class AvailableSystem(AdcResource[AvailableSystemAttributes]):
    """Object representing available systems."""

    resource_type = ResourceType.AVAILABLE_SYSTEM
    attributes_type = AvailableSystemAttributes
