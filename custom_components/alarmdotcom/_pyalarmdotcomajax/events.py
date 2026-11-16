"""General event broker for all events in the system."""

from __future__ import annotations

import asyncio
import logging
from asyncio import Task
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from functools import partial
from inspect import iscoroutinefunction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _pyalarmdotcomajax.models.base import AdcResource

log = logging.getLogger(__name__)


class EventBrokerTopic(Enum):
    """Resource event types for transmission from pyalarmdotcomajax."""

    # Controller Events
    RESOURCE_ADDED = "add"
    RESOURCE_UPDATED = "update"
    RESOURCE_DELETED = "delete"

    # Websocket Events
    RAW_RESOURCE_EVENT = "RESOURCE_EVENT"
    CONNECTION_EVENT = "CONNECTION_EVENT"
    DEVICE_ACTIVITY = "DEVICE_ACTIVITY"


@dataclass(kw_only=True)
class EventBrokerMessage:
    """Represent a message to be published."""

    topic: EventBrokerTopic


EventBrokerCallbackT = Callable[[EventBrokerMessage], Awaitable[None] | None]


class EventBroker:
    """Manage subscriptions and distribute messages to subscribers."""

    def __init__(self) -> None:
        self._subscriptions: dict[
            EventBrokerTopic, dict[EventBrokerCallbackT, list[str] | None]
        ] = {}
        self._background_tasks: set[Task] = set()

    def subscribe(
        self,
        topics: EventBrokerTopic | list[EventBrokerTopic],
        callback: EventBrokerCallbackT,
        ids: list[str] | str | None = None,
    ) -> Callable[[], None]:
        """Register a callback function to one or more topics."""

        if isinstance(topics, EventBrokerTopic):
            topics = [topics]

        if not ids:
            ids = []

        if isinstance(ids, str):
            ids = [ids]

        def unsubscribe_topic(
            topic: EventBrokerTopic, callback: EventBrokerCallbackT = callback
        ) -> None:  # Fixed closure issue
            """Unregister the callback from a specific topic."""
            if topic in self._subscriptions:
                del self._subscriptions[topic][callback]
                if not self._subscriptions[topic]:  # If list is empty, remove the entry
                    del self._subscriptions[topic]

        unsubscribe_functions = []
        for topic in topics:
            self._subscriptions.setdefault(topic, {})[callback] = ids
            unsubscribe_functions.append(partial(unsubscribe_topic, topic, callback))

        def unsubscribe_all() -> None:
            """Unregister the callback from all topics."""
            for unsubscribe_func in unsubscribe_functions:
                unsubscribe_func()

        return unsubscribe_all

    def publish(self, message: EventBrokerMessage) -> None:
        """
        Publish a message to subscribers of a topic.

        A subscriber that raises is logged and skipped. Letting the exception escape stopped delivery to every later
        subscriber, and since the websocket client and AlarmBridge.close() publish connection events, one broken
        entity could kill every reconnect and make the config entry fail to unload.
        """

        # Snapshot: a callback may unsubscribe itself (or another) while we iterate.
        for callback, ids in list(self._subscriptions.get(message.topic, {}).items()):
            if (
                hasattr(message, "id")
                and ids
                and getattr(message, "id", None) not in ids
            ):
                continue

            try:
                if iscoroutinefunction(callback):
                    task = asyncio.create_task(callback(message))
                    self._background_tasks.add(task)
                    task.add_done_callback(self._subscriber_done)
                else:
                    callback(message)
            except Exception:
                log.exception("Subscriber %r failed on %s; continuing with the others.", callback, message.topic)


    def _subscriber_done(self, task: Task) -> None:
        """Retrieve callback failures so one asynchronous subscriber cannot leak errors."""
        self._background_tasks.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            log.error("Asynchronous event subscriber failed", exc_info=(type(error), error, error.__traceback__))


#
# CONTROLLER EVENTS
#


@dataclass(kw_only=True)
class ResourceEventMessage(EventBrokerMessage):
    """Message class for updated resources."""

    id: str
    resource: AdcResource | None = None


#
# /CONTROLLER EVENTS
#


@dataclass(kw_only=True)
class DeviceActivityMessage(EventBrokerMessage):
    """A switch scene or camera classification, independent of state changes."""

    topic: EventBrokerTopic = EventBrokerTopic.DEVICE_ACTIVITY
    id: str
    event_type: int
    value: float | None = None
    extra: str = ""
