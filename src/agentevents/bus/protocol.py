from __future__ import annotations

from types import TracebackType
from typing import Any, Protocol, Self

from agentevents.models import Event, PayloadT

DEFAULT_QUEUE_SIZE = 100


class Subscription(Protocol[PayloadT]):
    """
    A live subscription to events matching a pattern.

    Used as an async context manager around iteration, so cleanup
    (deregistering from the bus) is guaranteed to run synchronously when
    the block exits — via falling through, `break`, or an exception —
    rather than depending on garbage-collection timing:

        async with bus.subscribe("deploy.*") as sub:
            async for event in sub:
                ...
                break  # unsubscribe() has already run once this line ends
    """

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

    def __aiter__(self) -> Self: ...

    async def __anext__(self) -> Event[PayloadT]: ...

    async def unsubscribe(self) -> None:
        """Deregister this subscription. Safe to call more than once."""
        ...


class EventBus(Protocol):
    async def publish(self, event: Event[Any]) -> None:
        """Publish an event to all matching subscribers."""
        ...

    def subscriber_count(self, pattern: str | None = None) -> int:
        """
        Return the number of active subscriptions.

        If pattern is given, only count subscriptions registered with that
        exact pattern string. This is a literal match against the pattern
        a subscriber passed to subscribe(), not a wildcard match against
        event types.
        """
        ...

    def subscribe(
        self,
        pattern: str,
        *,
        payload_type: type[PayloadT | dict[str, Any]] = dict,
        queue_size: int = DEFAULT_QUEUE_SIZE,
    ) -> Subscription[PayloadT]:
        """
        Subscribe to events whose event_type matches pattern.

        Returns a Subscription — use it as an async context manager to
        guarantee deterministic cleanup:

            async with bus.subscribe("error_rate.*") as sub:
                async for event in sub:
                    ...

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
