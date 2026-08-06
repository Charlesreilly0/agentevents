from collections.abc import AsyncIterator
from typing import Any, Protocol

from agentevents.models import Event, PayloadT

DEFAULT_QUEUE_SIZE = 100


class EventBus(Protocol):
    async def publish(self, event: Event[Any]) -> None:
        """Publish an event to all matching subscribers."""
        ...

    def subscribe(
        self,
        pattern: str,
        *,
        payload_type: type[PayloadT] = dict,
        queue_size: int = DEFAULT_QUEUE_SIZE,
    ) -> AsyncIterator[Event[PayloadT]]:
        """
        Subscribe to events whose event_type matches pattern.

        pattern supports "*" (one segment) and ">" (one-or-more trailing
        segments) wildcards, see agentevents.matching.matches.

        payload_type, if given, validates/coerces each event's payload into
        that type before yielding; mismatches are logged and skipped rather
        than raised, so one bad event doesn't kill the subscriber loop.

        queue_size bounds this subscriber's buffer. If the subscriber falls
        behind the publish rate, the oldest buffered event is dropped to
        make room for the newest — publish() never blocks on a slow
        subscriber.
        """
        ...
