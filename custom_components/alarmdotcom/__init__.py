"""The alarmdotcom integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from . import const as adci
from .controller import ADCIController

log = logging.getLogger(__name__)

PLATFORMS: list[str] = ["alarm_control_panel", "binary_sensor", "lock", "cover"]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Set up alarmdotcom controller from a config entry."""

    log.debug("%s: Initializing Alarmdotcom from config entry.", __name__)

    # As there currently is no way to import options from yaml
    # when setting up a config entry, we fallback to adding
    # the options to the config entry and pull them out here if
    # they are missing from the options.
    _async_import_options_from_data_if_missing(hass, config_entry)

    hass.data.setdefault(adci.DOMAIN, {})

    if adci.DOMAIN not in hass.data:
        # Print startup message
        log.info(adci.STARTUP_MESSAGE)

    controller = ADCIController(hass, config_entry)
    if not await controller.async_setup():
        log.error("%s: Failed to initialize controller.", __name__)
        return False

    log.debug("Alarmdotcom config options %s", dict(config_entry.options))

    # Delete devices from Home Assistant that are no longer present on Alarm.com.
    current_devices: set[str] = set()
    for device_id in controller.devices.get("entity_data", []):
        current_devices.add(device_id)

    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    ):
        for identifier in device_entry.identifiers:
            if (
                identifier
                or f"{identifier}_low_battery"
                or f"{identifier}_malfunction" in current_devices
            ):
                break
        else:
            device_registry.async_remove_device(device_entry.id)

    # Delete entities from Home Assistant that are no longer present on Alarm.com.
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):

        if (
            entity_entry.entity_id
            or f"{entity_entry.entity_id}_low_battery"
            or f"{entity_entry.entity_id}_malfunction" in current_devices
        ):
            break
        else:
            entity_registry.async_remove(entity_entry.id)

    # Store controller
    hass.data[adci.DOMAIN][config_entry.entry_id] = controller

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


def _async_import_options_from_data_if_missing(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> None:
    """Import options from configuration.yaml."""

    options = dict(entry.options)
    data = {}
    importable_options = [
        adci.CONF_FORCE_BYPASS,
        adci.CONF_NO_DELAY,
        adci.CONF_SILENT_ARM,
        adci.CONF_ARM_CODE,
    ]
    found = False
    for key in entry.data:
        if key in importable_options and key not in options:
            options[key] = entry.data[key]
            found = True
        else:
            data[key] = entry.data[key]

    if found:
        hass.config_entries.async_update_entry(entry, data=data, options=options)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok: bool = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        log.debug("%s: Unloaded Alarm.com config entry.", __name__)
        hass.data[adci.DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class ADCIEntity(CoordinatorEntity):  # type: ignore
    """Base class for ADC entities."""

    def __init__(
        self,
        controller: ADCIController,
        device_data: Any,
    ) -> None:
        """Initialize class."""
        super().__init__(controller._coordinator)
        self._controller: ADCIController = controller
        self._device = device_data

        self._attr_unique_id = device_data["unique_id"]
        self._attr_name = device_data["name"]

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return entity specific state attributes."""

        return {
            "mac_address": self._device.get("mac_address"),
            "raw_state_text": self._device.get("raw_state_text"),
        }

    @property
    def device_info(self) -> dict:
        """Return the device information."""

        return {
            "default_manufacturer": "Alarm.com",
            "name": self.name,
            "identifiers": {(adci.DOMAIN, self._device.get("unique_id"))},
            "via_device": (adci.DOMAIN, self._device.get("parent_id")),
        }

    async def async_added_to_hass(self) -> None:
        """Register updater for self._device when entity is added to Home Assistant."""
        # First, get updated state data.
        self.async_on_remove(
            self.coordinator.async_add_listener(self._update_device_data)
        )

        # Second, ask super to announce state update.
        await super().async_added_to_hass()

    def _update_device_data(self) -> None:

        updated = False

        try:
            device_data: dict | adci.ADCIGarageDoorData | adci.ADCILockData | adci.ADCIPartitionData | adci.ADCISensorData | adci.ADCISystemData = self._controller.devices.get(
                "entity_data", {}
            ).get(
                self.unique_id, {}
            )
            self._device = device_data

            updated = True

        except KeyError as err:
            log.error(
                "%s: Device database update failed for %s.", __name__, self._device
            )
            raise UpdateFailed from err

        if not updated:
            err_msg = (
                f"{__name__}: Failed to update data for {self._device.get('name')}."
            )

            log.error(err_msg)
            log.debug(device_data)

            raise UpdateFailed(err_msg)
