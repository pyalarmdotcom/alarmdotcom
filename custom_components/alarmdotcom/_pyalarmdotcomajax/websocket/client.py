"""Event controller."""

import asyncio
import contextlib
import json
import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Literal, NoReturn

import aiohttp
from _pyalarmdotcomajax.const import API_URL_BASE
from _pyalarmdotcomajax.events import DeviceActivityMessage, EventBrokerMessage, EventBrokerTopic
from _pyalarmdotcomajax.exceptions import (
    AuthenticationFailed,
    NotInitialized,
    OtpRequired,
    ServiceUnavailable,
    SessionExpired,
    UnexpectedResponse,
)
from _pyalarmdotcomajax.websocket.messages import (
    UNDEFINED,
    BaseWSMessage,
    EventWSMessage,
    PropertyChangeWSMessage,
    ResourceEventType,
    ResourcePropertyChangeType,
    WebSocketMessageTester,
)

if TYPE_CHECKING:
    from _pyalarmdotcomajax import AlarmBridge


ALL_TOKEN = "*"  # noqa: S105
ALL_TOKEN_T = Literal["*"]


KEEP_ALIVE_SIGNAL_INTERVAL_S = 60
# The reader never gives up (see _event_reader); this caps how long it waits between attempts, so service resumes
# within minutes of Alarm.com or the internet coming back.
MAX_RECONNECT_WAIT_S = 5 * 60

# Alarm.com's websocket token is short-lived: the server closes the connection
# with code 1008 ("rejected token") about five minutes after it is issued.
# Measured on a live system, uptimes were 5m08s, 5m11s, 5m15s, 5m28s and 5m54s
# across forty minutes - a metronome, not network trouble. Recovering from the
# kick took up to 2m38s because the first attempts to reconnect hang and time
# out, leaving the integration blind for roughly a third of its life and losing
# every event that arrived meanwhile (a websocket has no replay, and the
# periodic API refresh only reports current state - a door opened and closed
# during the gap is gone for good).
#
# So replace the connection before the server expires it, on our own schedule
# and with a fresh token, rather than waiting to be kicked off.
WS_TOKEN_LIFETIME_S = 4 * 60 + 30
WS_CONNECT_TIMEOUT_S = 10

# How long to wait for a websocket token. The request goes to www.alarm.com, whose aiohttp defaults would allow
# minutes per attempt, and during a planned replacement the old connection is already closed - every event in
# that time is lost while the client still reports CONNECTED. Timing out instead takes the reconnect path, which
# ends in RECONNECTED and a full refresh.
WS_TOKEN_FETCH_TIMEOUT_S = 15

# How many raw frames to keep for diagnostics. The old cap of 25 was useless on
# any real account: a household with three phones reporting geofence crossings
# (event type 555) produces a frame every few seconds, so the buffer covered
# barely a minute - measured at 64 seconds on the account this was raised for.
# The event being investigated had always aged out before anyone could download
# diagnostics. At ~200 bytes per frame this holds roughly 100 KB and, at that
# same chatty rate, something like twenty minutes of history.
EVENT_HISTORY_MAXLEN = 500
DEFAULT_SIGNALS_PER_SESSION_REFRESH = 1


log = logging.getLogger(__name__)


class WebSocketState(Enum):
    """Enum with possible Events."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    DEAD = "dead"
    WAITING = "waiting"

    # Only for emit
    RECONNECTED = "reconnected"


@dataclass(kw_only=True)
class RawResourceEventMessage(EventBrokerMessage):
    """Message class for updated resources."""

    topic: EventBrokerTopic = EventBrokerTopic.RAW_RESOURCE_EVENT
    ws_message: BaseWSMessage


@dataclass(kw_only=True)
class ConnectionEvent(EventBrokerMessage):
    """Message class for updated resources."""

    topic: EventBrokerTopic = EventBrokerTopic.CONNECTION_EVENT
    current_state: WebSocketState
    next_attempt_s: int | None = None


@dataclass
class SupportedResourceEvents:
    """Supported WebSocket Notifications."""

    state_change: bool = False
    geofence_crossing: bool = False
    events: list[ResourceEventType | ALL_TOKEN_T] = field(default_factory=list)
    property_changes: list[ResourcePropertyChangeType | ALL_TOKEN_T] = field(default_factory=list)


class WebSocketClient:
    """Control WebSocket connection and distribute messages."""

    def __init__(self, bridge: "AlarmBridge") -> None:
        """Initialize authentication controller."""
        self._bridge = bridge

        self._token: str | None = None
        self._ws_endpoint: str | None = None

        self._state = WebSocketState.DISCONNECTED

        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._background_tasks: list[asyncio.Task] = []

        self._last_session_refresh: datetime | None = None
        self._session_refresh_interval_ms: int | None = None
        self._keep_alive_url: str | None = None
        self._event_history: deque = deque(maxlen=EVENT_HISTORY_MAXLEN)

        self._initialized = False

    @property
    def connected(self) -> bool:
        """Whether client is connected to server."""

        return self.state in [WebSocketState.CONNECTED, WebSocketState.RECONNECTED]

    @property
    def state(self) -> WebSocketState:
        """Return connection state."""

        return self._state

    @property
    def last_events(self) -> list[dict]:
        """Return a list with the previous X messages."""

        return list(self._event_history)

    async def initialize(self) -> None:
        """
        Start listening for events.

        Connection will be auto-reconnected if it gets lost.
        """

        if not self._bridge.initialized:
            raise NotInitialized

        if self._initialized:
            return

        def emergency_stop(task: asyncio.Task) -> None:
            """Stop all background tasks and state reason."""

            if task.cancelled():
                log.debug("WebSocket client task %s was killed.", task.get_name())
            else:
                log.error(
                    "WebSocket client ran into an error with the %s task. Killing siblings.",
                    task.get_name(),
                )
                self.stop(WebSocketState.DEAD)

        if len(self._background_tasks) > 0:
            raise RuntimeError("Already initialized")

        self._background_tasks.append(asyncio.create_task(self._event_reader(), name="Event Reader"))
        self._background_tasks.append(asyncio.create_task(self._event_processor(), name="Event Processor"))
        self._background_tasks.append(asyncio.create_task(self._keep_alive(), name="Keep Alive"))

        for task in self._background_tasks:
            task.add_done_callback(emergency_stop)

        self._initialized = True

    def stop(self, state: WebSocketState = WebSocketState.DISCONNECTED) -> None:
        """Stop listening for events."""

        if self._background_tasks:
            log.debug("Stopping Alarm.com WebSocket client (state: %s).", state.value)
        self._set_state(state)

        for task in self._background_tasks:
            task.cancel()

        self._background_tasks = []

        self._initialized = False

    #############################
    # NOTIFICATION TRANSMISSION #
    #############################

    def _emit_ws_state(self, state: WebSocketState, next_attempt_s: int | None = None) -> None:
        """Emit connection event to all listeners."""

        self._bridge.events.publish(ConnectionEvent(current_state=state, next_attempt_s=next_attempt_s))

    def _emit_resource(self, data: BaseWSMessage) -> None:
        """Emit resource event to all listeners."""

        self._bridge.events.publish(RawResourceEventMessage(ws_message=data))

    #################################
    # LONG-RUNNING BACKGROUND TASKS #
    #################################

    async def _event_reader(self) -> NoReturn:
        """Maintain connection with server and read events from stream."""

        self._set_state(WebSocketState.CONNECTING)
        connect_attempts = 0

        while True:
            connect_attempts += 1

            stage = "token fetch"
            stage_started = time.monotonic()
            try:
                async with asyncio.timeout(WS_TOKEN_FETCH_TIMEOUT_S):
                    await self._authenticate()

                log.info("[EVENT READER] Connecting to Alarm.com WebSocket endpoint...")

                # The token's lifetime starts when it is issued, not when
                # the WebSocket handshake completes.
                token_issued_at = time.monotonic()
                stage = "handshake"
                stage_started = token_issued_at
                planned_refresh = False
                async with contextlib.AsyncExitStack() as connection:
                    async with asyncio.timeout(WS_CONNECT_TIMEOUT_S):
                        websocket = await connection.enter_async_context(
                            self._bridge.ws_connect(f"{self._ws_endpoint}/?f=1&auth={self._token}")
                        )
                    stage = "event stream"
                    stage_started = time.monotonic()
                    self._set_state(
                        WebSocketState.CONNECTED if connect_attempts == 1 else WebSocketState.RECONNECTED,
                    )

                    if connect_attempts == 1:
                        # A first connection or a planned replacement. Neither emits RECONNECTED, so no
                        # controller refreshes, yet events were lost in both gaps: between the initial state
                        # fetch and this connection, and while the old connection closed and this one opened.
                        # (RECONNECTED already triggers a full refresh in every controller.)
                        self._bridge.request_reconcile("websocket connected")

                    connect_attempts = 1
                    log.info("[EVENT READER] Connected to WebSocket")
                    remaining = max(0, WS_TOKEN_LIFETIME_S - (time.monotonic() - token_issued_at))
                    try:
                        async with asyncio.timeout(remaining) as deadline:
                            await self._read_messages(websocket)
                    except TimeoutError:
                        if not deadline.expired():
                            raise
                        planned_refresh = True
                        log.debug("[EVENT READER] Rotating WebSocket before token expiry.")

                if planned_refresh:
                    connect_attempts = 0
                    continue

                if log.isEnabledFor(logging.DEBUG):
                    close_code: aiohttp.WSCloseCode | int | None = websocket.close_code
                    with contextlib.suppress(AttributeError):
                        if websocket.close_code:
                            # Code 1008 indicates token rejection; proactive rotation should preempt it.
                            close_code = aiohttp.WSCloseCode(int(websocket.close_code))

                    log.debug("[EVENT READER] WebSocket Connection Closed (%s)", close_code)

            except OtpRequired:
                log.error(
                    "[EVENT READER] Server requested OTP when attempting to keep session alive. This was most likely caused by an issue extracting the MFA token during sign-in."
                )
                raise
            except (AuthenticationFailed, SessionExpired):
                # Token request failed.
                log.debug(
                    "[EVENT READER] Failed to authenticate WebSocket connection. This is likely due to a session timeout."
                )
            except (TimeoutError, aiohttp.ClientError, UnexpectedResponse) as err:
                # status = 401 (HTTP):                      WebSocket Authentication failure
                # errno = 104 (Socket errno.ECONNRESET):    Connection reset by peer
                log.debug(
                    "[EVENT READER] WebSocket %s failed after %.2fs (%s). Attempting to recover."
                    "\nHTTP STATUS: %s\nSOCKET ERRNO: %s",
                    stage,
                    time.monotonic() - stage_started,
                    type(err).__name__,
                    getattr(err, "status", None),
                    getattr(err, "errno", None),
                )
            except Exception as err:
                # for debugging purpose only
                log.exception("[EVENT READER] Fatal Error")
                raise err  # noqa: TRY201

            # No attempt limit. Stopping here used to end the reader for good after 25 failures (about half an
            # hour of an Alarm.com or internet outage) while emitting DISCONNECTED rather than DEAD, so nothing
            # restarted it and Home Assistant kept reporting the integration available with no live updates.

            reconnect_wait = round(
                min(10 * connect_attempts * random.random(), MAX_RECONNECT_WAIT_S)  # noqa: S311
            )

            log.debug(
                "[EVENT READER] WebSocket Disconnected - Reconnect attempt %s will be attempted in %s seconds.",
                connect_attempts,
                reconnect_wait,
            )

            self._set_state(WebSocketState.DISCONNECTED, reconnect_wait)

            # every 10 failed connect attempts log warning
            if connect_attempts % 10 == 0:
                log.warning(
                    "[EVENT READER] %s attempts to (re)connect Alarm.com WebSocket endpoint failed.",
                    connect_attempts,
                )

            self._set_state(WebSocketState.WAITING)

            await asyncio.sleep(reconnect_wait)

    async def _read_messages(self, websocket: aiohttp.ClientWebSocketResponse) -> None:
        """Read and retain WebSocket events until disconnected or rotated."""
        async for msg in websocket:
            if msg.type == aiohttp.WSMsgType.CLOSED:
                log.info(
                    "[EVENT READER] WebSocket closed: Code: %s, Message: '%s'",
                    msg.data,
                    msg.extra,
                )
                continue
            if msg.type == aiohttp.WSMsgType.ERROR:
                log.info("[EVENT READER] WebSocket error: '%s'", msg.data)
                continue
            if msg.type != aiohttp.WSMsgType.TEXT:
                log.debug("[EVENT READER] Non-text WebSocket message: '%s'", msg.data)
                continue
            self._event_queue.put_nowait(msg.data)
            self._event_history.append(msg.data)

    def _emit_device_activity(self, payload: object) -> bool:
        """Decode confirmed scene and video events from either ADC field casing."""
        if not isinstance(payload, dict):
            return False
        fields = {str(key).replace("_", "").lower(): value for key, value in payload.items()}
        try:
            event_type = int(fields.get("eventtype", -1))
        except (TypeError, ValueError):
            return False
        if event_type not in (163, 71, 210):
            return False
        unit = fields.get("unitid")
        device = fields.get("deviceid")
        if unit is None or device is None:
            return False
        resource_id = str(device) if "-" in str(device) else f"{unit}-{device}"
        try:
            value = float(fields["eventvalue"]) if fields.get("eventvalue") is not None else None
        except (TypeError, ValueError):
            value = None
        self._bridge.events.publish(
            DeviceActivityMessage(
                id=resource_id,
                event_type=event_type,
                value=value,
                extra=str(fields.get("qstringforextradata") or ""),
            )
        )
        return True

    async def _event_processor(self) -> NoReturn:
        """Process incoming events."""

        while True:
            try:
                msg_json: str = str(await self._event_queue.get())

                if self._emit_device_activity(json.loads(msg_json)):
                    continue
                msg_tester = WebSocketMessageTester.from_json(msg_json)

                # log.debug("Tester message: %s", msg_tester)

                converted_message: BaseWSMessage | None = None

                log.debug("[EVENT PROCESSOR] Received WebSocket Message: %s", msg_json)

                # Determine and set message type class.
                # Skipped message types seem to be unused by Alarm.com's webapp. The same actions
                # are instead handled via event messages.

                if UNDEFINED not in [
                    msg_tester.event_type,
                    msg_tester.event_value,
                    msg_tester.qstring_for_extra_data,
                    msg_tester.event_date_utc,
                ]:
                    converted_message = EventWSMessage.from_json(msg_json)
                elif UNDEFINED not in [
                    msg_tester.event_type,
                    msg_tester.correlated_id,
                ]:
                    # converted_message = MonitoringEventWSMessage.from_json(msg_json)
                    # These messages will be picked up as EventWSMessage, and that's fine.
                    # Device WS controllers will need to interpret them the same way.
                    continue
                elif UNDEFINED not in [msg_tester.property_, msg_tester.property_value]:
                    converted_message = PropertyChangeWSMessage.from_json(msg_json)
                elif UNDEFINED not in [msg_tester.fence_id, msg_tester.is_inside_now]:
                    # converted_message = GeofenceCrossingWSMessage.from_json(msg_json)
                    continue
                elif UNDEFINED not in [msg_tester.new_state, msg_tester.flag_mask]:
                    # converted_message = StatusUpdateWSMessage.from_json(msg_json)
                    continue

                log.debug(
                    "[EVENT PROCESSOR] WebSocket message type identified as %s",
                    converted_message.__class__.__name__,
                )

                if converted_message:
                    self._emit_resource(converted_message)
                else:
                    log.warning(
                        "[EVENT PROCESSOR] Unprocessable message received: %s",
                        json.loads(msg_json),
                    )

            except Exception:
                # Never parse the malformed payload again in this error handler:
                # doing so can kill the processor and freeze subsequent sensor updates.
                log.exception("[EVENT PROCESSOR] Failed to convert message.")
                log.debug("[EVENT PROCESSOR] Rejected payload: %s", msg_json)

    async def _keep_alive(self) -> NoReturn:
        """
        Keep session alive.

        Alarm.com's webapp uses the keep alive to handle session timeouts. We'll use the event reader to do that, instead.
        """

        # Determine number of keep_alives to send between session refreshes.
        session_refresh_interval_ms = self._bridge.auth_controller.session_refresh_interval_ms
        session_refresh_interval = max(
            int(session_refresh_interval_ms / (KEEP_ALIVE_SIGNAL_INTERVAL_S * 1000)),
            DEFAULT_SIGNALS_PER_SESSION_REFRESH,
        )

        log.info(
            "[KEEP ALIVE] Session refresh interval: %s ms / %s pings",
            session_refresh_interval_ms,
            session_refresh_interval,
        )

        signals_sent = 0

        while True:
            await asyncio.sleep(KEEP_ALIVE_SIGNAL_INTERVAL_S)

            # Don't send requests if websocket client is disconnected.
            #
            # `connected`, not `state == CONNECTED`: the event reader reports
            # CONNECTED only for the very first connection and RECONNECTED for
            # every one after that, and never returns to CONNECTED (see
            # _event_reader). Comparing against CONNECTED alone therefore
            # silenced the keep-alive permanently from the first reconnect
            # onward, leaving the Alarm.com session to idle out and every later
            # request to depend on the bridge's login-repair path.
            if not self.connected:
                log.debug("[KEEP ALIVE] Skipping keep alive.")
                signals_sent = 0
                continue

            log.debug("[KEEP ALIVE] Sending keep alive.")

            try:
                if signals_sent >= session_refresh_interval - 1:
                    signals_sent = 0
                    await self._reload_session_context()
                if self._bridge.auth_controller.enable_keep_alive and not await self._bridge.is_logged_in():
                    log.info("[Keep Alive] Detected expired user session.")
            except Exception:
                # All connection error handling managed by event reader.
                log.debug("[KEEP ALIVE] Error while sending keep alive.", exc_info=True)

            signals_sent += 1

    #####################
    # REQUEST FUNCTIONS #
    #####################

    async def _authenticate(self) -> None:
        """Get authentication token for websocket endpoint."""

        log.info("Getting WebSocket token.")

        self._token = None

        try:
            response = await self._bridge.get(path="websockets/token", id=None, mini_response=True)
        except AuthenticationFailed:
            # _bridge.get autorepairs when logged out, so we should re-raise AuthenticationFailed.
            log.debug("Primary session expired. Bailing on getting new token.")
            raise
        except (ServiceUnavailable, UnexpectedResponse):
            log.debug("Failed to connect to Alarm.com when authenticating. Try again later.")
            return

        try:
            self._ws_endpoint = response.metadata["endpoint"]
        except KeyError as err:
            raise UnexpectedResponse("Failed to get WebSocket endpoint.") from err

        # Set token only after we have a valid websocket endpoint.
        self._token = response.value

    async def _reload_session_context(self) -> None:
        """Check if we are still logged in."""

        log.info("Reloading session context.")

        url = f"{API_URL_BASE}identities/{self._bridge.auth_controller.profile_id}/reloadContext"
        payload = {"included": [], "meta": {"transformer_version": "1.1"}}

        async with self._bridge.create_request("post", url, json=payload, raise_for_status=True) as rsp:
            text_rsp = await rsp.text()

            if rsp.status >= 400:
                raise UnexpectedResponse(f"Failed to reload session context. Response: {text_rsp}")

        log.debug("Reloaded context. Fetching new token...")

        await self._authenticate()

    def _set_state(self, state: WebSocketState, reconnect_wait: int | None = None) -> None:
        """Set WS client state and emit message only if state has changed."""

        async def emit_state_after_delay(delay: int) -> None:
            """Non-blocking function that emits state after a delay."""
            await asyncio.sleep(delay)
            if self._state == WebSocketState.CONNECTED:
                self._emit_ws_state(WebSocketState.RECONNECTED, None)
            else:
                log.debug("Skipping reconnect emit. No longer connected.")

        if self._state != state:
            self._state = WebSocketState.CONNECTED if state == WebSocketState.RECONNECTED else state

            if state == WebSocketState.RECONNECTED:
                # Only emit reconnects after 5 second delay. This prevents downstream reconnect events from
                # triggering if the Alarm.com server connects, then immediately drops the connection.
                self._background_tasks.append(asyncio.create_task(emit_state_after_delay(5)))
            else:
                self._emit_ws_state(state, reconnect_wait)
