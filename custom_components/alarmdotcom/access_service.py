"""Home Assistant action for an existing Alarm.com user's temporary access."""

from __future__ import annotations

from typing import TYPE_CHECKING

from _pyalarmdotcomajax.access import AccessValidationError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN
from .schema import vol

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse

SERVICE_SET_TEMPORARY_ACCESS = "set_temporary_access"
SERVICE_GET_TEMPORARY_USER_SCHEDULE = "get_temporary_user_schedule"


def async_register_access_service(hass: HomeAssistant) -> None:
    """Register once, resolving the live account for every invocation."""
    if (hass.services.has_service(DOMAIN, SERVICE_SET_TEMPORARY_ACCESS)
            and hass.services.has_service(DOMAIN, SERVICE_GET_TEMPORARY_USER_SCHEDULE)):
        return

    async def handle(call: ServiceCall) -> None:
        """Route explicitly to a loaded account, never the first registered hub."""
        entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Select a loaded Alarm.com configuration entry.")
        hub = entry.runtime_data.hub
        system_id = call.data["system_id"]
        if not any(system.id == system_id for system in hub.api.systems):
            raise ServiceValidationError("System ID does not belong to the selected Alarm.com account.")
        try:
            await hub.api.device_access.set_temporary_access(
                call.data["user_id"], system_id, call.data["begin"], call.data["end"],
            )
        except AccessValidationError as err:
            raise ServiceValidationError(str(err)) from None
        except Exception:
            # HTTP/parser exceptions may embed private server content. Do not
            # put their text or traceback into an automation trace or log.
            raise HomeAssistantError(
                "Could not confirm the access update. Check the Alarm.com portal before retrying."
            ) from None

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_TEMPORARY_ACCESS,
        handle,
        schema=vol.Schema({
            vol.Required("config_entry_id"): cv.string,
            vol.Required("system_id"): cv.string,
            vol.Required("user_id"): cv.string,
            vol.Required("begin"): cv.datetime,
            vol.Required("end"): cv.datetime,
        }),
    )

    async def read_schedule(call: ServiceCall) -> ServiceResponse:
        """Read from the selected live account and return only public fields."""
        entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Select a loaded Alarm.com configuration entry.")
        hub = entry.runtime_data.hub
        system_id = call.data["system_id"]
        if not any(system.id == system_id for system in hub.api.systems):
            raise ServiceValidationError("System ID does not belong to the selected Alarm.com account.")
        try:
            result: ServiceResponse = await hub.api.device_access.get_temporary_user_schedule(
                call.data["user_id"], system_id,
            )
        except AccessValidationError as err:
            raise ServiceValidationError(str(err)) from None
        except Exception:
            raise HomeAssistantError("Could not read the access schedule from Alarm.com.") from None
        return result

    hass.services.async_register(
        DOMAIN, SERVICE_GET_TEMPORARY_USER_SCHEDULE, read_schedule,
        schema=vol.Schema({
            vol.Required("config_entry_id"): cv.string,
            vol.Required("system_id"): cv.string,
            vol.Required("user_id"): cv.string,
        }),
        supports_response=SupportsResponse.ONLY,
    )
