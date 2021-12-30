"""Interfaces with Alarm.com alarm locks."""
import logging
import re

from pyalarmdotcomajax import Alarmdotcom, AlarmdotcomADT, AlarmdotcomProtection1
import voluptuous as vol

import homeassistant.components.lock as lock

try:
    from homeassistant.components.lock import LockEntity
except ImportError:
    from homeassistant.components.lock import (
        Lock as LockEntity,
    )

from homeassistant.components.lock import PLATFORM_SCHEMA

from homeassistant.const import (
    CONF_CODE,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_JAMMED,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
    STATE_UNKNOWN
)
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Alarm.com"
CONF_ADT = "adt"
CONF_PROTECTION1 = "protection1"
CONF_TWO_FACTOR_COOKIE = "two_factor_cookie"
DOMAIN = "alarmdotcom"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_CODE): cv.string,
        vol.Optional(CONF_ADT, default=False): cv.boolean,
        vol.Optional(CONF_PROTECTION1, default=False): cv.boolean,
        vol.Optional(CONF_TWO_FACTOR_COOKIE): cv.string,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    code = config.get(CONF_CODE)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    two_factor_cookie = config.get(CONF_TWO_FACTOR_COOKIE)
    use_new_websession = hass.data.get(DOMAIN)
    adt_or_protection1 = 0
    if config.get(CONF_ADT):
        adt_or_protection1 = 1
    elif config.get(CONF_PROTECTION1):
        adt_or_protection1 = 2
    if not use_new_websession:
        hass.data[DOMAIN] = True
        use_new_websession = False
    
    if use_new_websession:
            websession = async_create_clientsession(hass)
            _LOGGER.debug("Using new websession.")
    else:
        websession = async_get_clientsession(hass)
        _LOGGER.debug("Using hass websession.")
    if adt_or_protection1 == 1:
        adc_class = AlarmdotcomADT
    elif adt_or_protection1 == 2:
        adc_class = AlarmdotcomProtection1
    else:
        adc_class = Alarmdotcom

    _LOGGER.debug("Setting up Alarm.com...")
    alarmdotcom = adc_class(
        username,
        password,
        websession,
        False,
        False,
        False,
        two_factor_cookie,
    )

    await alarmdotcom.async_login()
    await alarmdotcom.async_update()

    _LOGGER.debug("Acquiring locks...")
    locks = []
    for lock_id in alarmdotcom.lock_ids:
        lockDescription = alarmdotcom.sensor_status_detailed[lock_id]["description"]
        _LOGGER.debug("Adding lock `{}` with ID `{}`...", lockDescription, lock_id)
        locks.append(AlarmDotComLock(
            lock_id,
            lockDescription,
            code,
            alarmdotcom
        ))
    
    _LOGGER.debug("Registering adding lock entities...")
    async_add_entities(locks)


class AlarmDotComLock(LockEntity):
    def __init__(
        self,
        lock_id,
        name,
        code,
        alarmdotcom,
    ):
        self._lock_id = lock_id
        self._name = name
        self._code = code if code else None
        self._alarmdotcom = alarmdotcom

    async def async_update(self):
        """Fetch the latest state."""
        await self._alarmdotcom.async_update("lock")
        return self._alarmdotcom.state[self._lock_id]

    @property
    def name(self):
        """Return the name of the lock."""
        return self._name

    @property
    def unique_id(self) -> str:
        return self._lock_id

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        if self._code is None:
            return None
        if isinstance(self._code, str) and re.search("^\\d+$", self._code):
            return "number"
        return "text"

    @property
    def state(self):
        """Return the state of the device."""
        try:
            lock_state = self._alarmdotcom.state[self._lock_id]
        except KeyError:
            return STATE_UNKNOWN

        if lock_state.lower() == "unlocked":
            return STATE_UNLOCKED
        if lock_state.lower() == "locked":
            return STATE_LOCKED
        return STATE_UNKNOWN

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"sensor_status": self._alarmdotcom.sensor_status}

    async def async_lock(self, code=None):
        """Send lock command."""
        if self._validate_code(code):
            await self._alarmdotcom.async_lock(self._lock_id)

    async def async_unlock(self, code=None):
        """Send unlock command."""
        if self._validate_code(code):
            await self._alarmdotcom.async_unlock(self._lock_id)

    def _validate_code(self, code):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Wrong code entered")
        return check
