"""Authentication management."""

import asyncio
import logging
import re
from typing import TYPE_CHECKING

import aiohttp
from _pyalarmdotcomajax import const
from _pyalarmdotcomajax.controllers.users import (
    DealersController,
    IdentitiesController,
    ProfilesController,
)
from _pyalarmdotcomajax.exceptions import (
    AuthenticationFailed,
    MustConfigureMfa,
    OtpRequired,
    ServiceUnavailable,
    UnexpectedResponse,
)
from _pyalarmdotcomajax.models.auth import (
    OtpType,
    TwoFactorAuthentication,
)
from _pyalarmdotcomajax.models.jsonapi import Resource
from _pyalarmdotcomajax.util import resources_pretty, resources_raw
from bs4 import BeautifulSoup
from rich.console import Group

if TYPE_CHECKING:
    from _pyalarmdotcomajax import AlarmBridge

VIEWSTATE_FIELD = "__VIEWSTATE"
VIEWSTATEGENERATOR_FIELD = "__VIEWSTATEGENERATOR"
EVENTVALIDATION_FIELD = "__EVENTVALIDATION"
PREVIOUSPAGE_FIELD = "__PREVIOUSPAGE"

TWO_FACTOR_PATH = "engines/twoFactorAuthentication/twoFactorAuthentications"

log = logging.getLogger(__name__)

#
# API AVAILABLE SYSTEM RESPONSE
#

#
# Known Issues:
#
# 1.    Identities, Profiles, and Dealers are only loaded when a user first logs in.
#       Once an auth cookie is stored and the user is logged in, these resources
#       are not reloaded.
#
# 2.    We ignore all identities except the first one. This is lazy and will
#       cause trouble for users with multiple identities.
#


class AuthenticationController:
    """Controller for user identity."""

    def __init__(
        self,
        bridge: "AlarmBridge",
        username: str | None = None,
        password: str | None = None,
        mfa_cookie: str | None = None,
    ) -> None:
        """Initialize authentication controller."""
        self._bridge = bridge

        # Credentials
        # We allow these to be set after initialization so that we can use an instantiated (but not initialized)
        # AlarmBridge to populate the adc cli command list.
        self._username: str = username or ""
        self._password: str = password or ""
        self.mfa_cookie: str = mfa_cookie or ""

        # Device Controllers
        self._identities = IdentitiesController(self._bridge)
        self._profiles = ProfilesController(self._bridge, self._identities)
        self._dealers = DealersController(self._bridge)

    @property
    def resources_pretty(self) -> "Group":
        """Return pretty Rich representation of resources in controller."""

        return resources_pretty("Users", [*self._identities.items, *self._profiles.items])

    @property
    def resources_raw(self) -> "Group":
        """Return Rich representation raw JSON for all controller resources."""

        return resources_raw("Users", [*self._identities.items, *self._profiles.items])

    @property
    def included_raw_str(self) -> "Group":
        """Return Rich representation of raw JSON for all controller resources."""

        return resources_raw("Users Children", [*self._identities.items, *self._profiles.items])

    @property
    def has_trouble_conditions_service(self) -> bool:
        """Whether the user has access to the trouble conditions service."""

        return self._identities.items[0].attributes.has_trouble_conditions_service

    @property
    def dealer(self) -> str | None:
        """The name of the Alarm.com provider."""

        return self._dealers.items[0].attributes.name or "Alarm.com"

    @property
    def user_email(self) -> str | None:
        """The user's email address."""

        return self._profiles.items[0].attributes.email

    @property
    def session_refresh_interval_ms(self) -> int:
        """Interval at which session should be refreshed in milliseconds."""

        return (
            self._identities.items[0].attributes.application_session_properties.inactivity_warning_timeout_ms
            or 5 * 60 * 1000
        )  # Default: 5 minutes

    @property
    def keep_alive_url(self) -> str | None:
        """URL for keep-alive requests, if keep alive is enabled."""

        return self._identities.items[0].attributes.application_session_properties.keep_alive_url

    @property
    def use_celsius(self) -> bool:
        """Whether the user uses celsius or fahrenheit."""

        try:
            return self._identities.items[0].attributes.localize_temp_units_to_celsius
        except (AttributeError, IndexError):
            log.error("Could not find temperature unit preference.")
            return False

    @property
    def profile_id(self) -> str:
        """The user's profile ID."""

        return self._profiles.items[0].id

    @property
    def enable_keep_alive(self) -> bool:
        """Whether keep-alive is enabled."""

        return (
            self._identities.items[0].attributes.application_session_properties.enable_keep_alive
            if self._identities.items[0].attributes.application_session_properties.enable_keep_alive is not None
            else True
        )

    def set_credentials(self, username: str, password: str, mfa_cookie: str | None = None) -> None:
        """Set the user's credentials."""

        self._username = username
        self._password = password
        self.mfa_cookie = mfa_cookie or ""

    async def login(self) -> None:
        """
        Log in to Alarm.com.

        Raises:
            AuthenticationFailed: If login fails.
            ServiceUnavailable: If the service is unavailable.
            UnexpectedResponse: If an unexpected response is received.
            OtpRequired: If two-factor authentication is required.

        """
        log.debug("Logging in to Alarm.com")

        if "" in [self._username, self._password]:
            raise AuthenticationFailed("Username and password are required.")

        self._bridge.ajax_key = None

        #
        # Step 1: Get login page and cookies
        #

        login_info = await self._login_preload()

        #
        # Step 2: Log in and save first anti-forgery key
        #

        await self._login_submit_credentials(login_info)

        log.debug("Logged in to Alarm.com.")

        #
        # Step 3: Determine whether OTP is required
        #

        log.debug("Checking MFA requirements.")

        await self._login_otp_discovery()

    ###################
    # LOGIN FUNCTIONS #
    ###################

    async def _login_preload(self) -> dict[str, str]:
        """Step 1 of login process. Get login page and cookies."""

        retries = 0
        while True:
            try:
                # Load login page once and grab hidden fields and cookies
                async with self._bridge.create_request(
                    method="get",
                    accept_types=const.ResponseTypes.HTML,
                    use_ajax_key=False,
                    url=f"{const.URL_BASE}login",
                ) as resp:
                    resp.raise_for_status()

                    text = await resp.text()

                    tree = BeautifulSoup(text, "html.parser")
                    return {
                        VIEWSTATE_FIELD: str(tree.select(f"#{VIEWSTATE_FIELD}")[0].attrs.get("value")),
                        VIEWSTATEGENERATOR_FIELD: str(
                            tree.select(f"#{VIEWSTATEGENERATOR_FIELD}")[0].attrs.get("value")
                        ),
                        EVENTVALIDATION_FIELD: str(tree.select(f"#{EVENTVALIDATION_FIELD}")[0].attrs.get("value")),
                        PREVIOUSPAGE_FIELD: str(tree.select(f"#{PREVIOUSPAGE_FIELD}")[0].attrs.get("value")),
                    }

            # Only retry for connection/server errors. No expectation of being logged in here, so we don't need to
            # single out authentication errors.
            except (TimeoutError, aiohttp.ClientResponseError) as err:
                if retries == const.REQUEST_RETRY_LIMIT:
                    raise ServiceUnavailable from err

                retries += 1
                continue

            except (AttributeError, IndexError, Exception) as err:
                raise UnexpectedResponse from err

    async def _login_submit_credentials(self, login_info: dict[str, str]) -> None:
        """Step 2 of login process. Submit credentials and get anti-forgery key."""

        retries = 0
        while True:
            try:
                # login and grab ajax key
                async with self._bridge.create_request(
                    method="post",
                    accept_types=const.ResponseTypes.FORM,
                    use_ajax_key=True,
                    url=f"{const.URL_BASE}web/Default.aspx",
                    data={
                        "ctl00$ContentPlaceHolder1$loginform$txtUserName": self._username,
                        "txtPassword": self._password,
                        VIEWSTATE_FIELD: login_info[VIEWSTATE_FIELD],
                        VIEWSTATEGENERATOR_FIELD: login_info[VIEWSTATEGENERATOR_FIELD],
                        EVENTVALIDATION_FIELD: login_info[EVENTVALIDATION_FIELD],
                        PREVIOUSPAGE_FIELD: login_info[PREVIOUSPAGE_FIELD],
                        "__EVENTTARGET": None,
                        "__EVENTARGUMENT": None,
                        "__VIEWSTATEENCRYPTED": None,
                        "IsFromNewSite": "1",
                    },
                    raise_for_status=True,
                ) as resp:
                    if re.search("m=login_fail", str(resp.url)) is not None:
                        raise AuthenticationFailed
                    if re.search("m=LockedOut", str(resp.url)) is not None:
                        raise AuthenticationFailed("Account is locked.")
                    return

            except AuthenticationFailed:
                # Alarm.com said no: wrong credentials or a locked account.
                raise

            # Only Alarm.com's own verdict above means the credentials are bad. A server error or a dropped
            # connection says nothing about them, and reporting it as an authentication failure sends Home
            # Assistant to "reauthentication required", which it never retries on its own.
            except (TimeoutError, aiohttp.ClientConnectionError) as err:
                if retries == const.REQUEST_RETRY_LIMIT:
                    raise ServiceUnavailable from err
                retries += 1
                continue

            except aiohttp.ClientResponseError as err:
                if err.status >= 500 or err.status == 429:
                    if retries == const.REQUEST_RETRY_LIMIT:
                        raise ServiceUnavailable from err
                    retries += 1
                    continue
                raise AuthenticationFailed from err

            except Exception as err:
                raise UnexpectedResponse from err

    async def _login_otp_discovery(self) -> None:
        """Step 3 of login process. Determine whether OTP is required."""

        # User ID required to check OTP status
        await asyncio.gather(
            self._identities.initialize(),
            self._profiles.initialize(),
            self._dealers.initialize(),
        )

        if not self._identities.items:
            raise UnexpectedResponse("No identities found.")

        if dealer_id := self._identities.items[0].dealer_id:
            log.debug(await self._dealers.add_target(dealer_id))
        else:
            log.error("No dealer ID found.")

        response = await self._bridge.get(path=TWO_FACTOR_PATH, id=self._identities.items[0].id)

        if not isinstance(response.data, Resource):
            raise UnexpectedResponse

        mfa_details = TwoFactorAuthentication(response.data)

        if mfa_details.attributes.show_suggested_setup is True:
            raise MustConfigureMfa

        enabled_otp_types_bitmask = mfa_details.attributes.enabled_two_factor_types

        if not mfa_details.attributes.is_2fa_enabled:
            return

        enabled_2fa_methods = [
            otp_type
            for otp_type in OtpType
            if enabled_otp_types_bitmask and bool((enabled_otp_types_bitmask) & otp_type.value)
        ]

        if (
            (OtpType.disabled in enabled_2fa_methods)
            or mfa_details.attributes.is_current_device_trusted is True
            or not enabled_otp_types_bitmask
            or not enabled_2fa_methods
        ):
            # 2FA is disabled (or the mfa token was accepted), we can skip 2FA altogether.
            return

        log.info(
            "Requires two-factor authentication. Enabled methods are %s",
            enabled_2fa_methods,
        )

        raise OtpRequired(
            enabled_2fa_methods,
            email=mfa_details.attributes.email,
            sms_country_code=mfa_details.attributes.sms_mobile_number.country
            if mfa_details.attributes.sms_mobile_number
            else None,
            sms_number=mfa_details.attributes.sms_mobile_number.mobile_number
            if mfa_details.attributes.sms_mobile_number
            else None,
        )

    #################
    # MFA FUNCTIONS #
    #################

    async def request_otp(self, method: OtpType | None) -> None:
        """Request e-mail or SMS OTP."""

        if method not in [OtpType.sms, OtpType.email]:
            return

        await self._bridge.post(
            path=TWO_FACTOR_PATH,
            id=self._identities.items[0].id,
            action="sendTwoFactorAuthenticationCodeViaSms"
            if method == OtpType.sms
            else "sendTwoFactorAuthenticationCodeViaEmail",
            mini_response=True,
        )

    async def submit_otp(self, code: str, method: OtpType, device_name: str | None = None) -> str | None:
        """Submit OTP and register device."""

        # An incorrect code makes verifyTwoFactorCode return a non-200 mini response, which the
        # bridge raises as AuthenticationFailed/NotAuthorized before we get here. So reaching the
        # next line means the code itself was accepted.
        await self._bridge.post(
            path=TWO_FACTOR_PATH,
            id=self._identities.items[0].id,
            action="verifyTwoFactorCode",
            json={"code": code, "typeOf2FA": method.value},
            mini_response=True,
        )

        # Register/trust this device. Besides "remembering" the device, the trustTwoFactorDevice
        # response is where Alarm.com reliably returns the twoFactorAuthenticationId (MFA) cookie,
        # so we run it whenever a device name is available. The cookie is harvested into
        # self.mfa_cookie by the bridge's request handler (from the response or the session cookie
        # jar) as these requests execute.
        if device_name:
            try:
                await self._bridge.post(
                    path=TWO_FACTOR_PATH,
                    id=self._identities.items[0].id,
                    action="trustTwoFactorDevice",
                    json={"deviceName": device_name},
                    mini_response=True,
                )
            except Exception:
                # Best-effort: don't let a trust-step failure mask a successful verification if the
                # MFA cookie was already collected. We re-check for the cookie below.
                log.warning(
                    "Device trust registration failed. This device may not be remembered and you "
                    "could be prompted for OTP again on the next login.",
                    exc_info=True,
                )
        else:
            log.debug("Skipping device registration (no device name provided).")

        # Validate only after both requests have had a chance to set the cookie.
        if not self.mfa_cookie:
            raise UnexpectedResponse("Could not find MFA cookie after submitting OTP code.")

        return self.mfa_cookie
