import asyncio
import logging
from types import TracebackType
from typing import Any

from pydantic import TypeAdapter

from agentevents.bus.protocol import DEFAULT_QUEUE_SIZE
from agentevents.matching import matches, validate_pattern
from agentevents.models import Event, PayloadT

logger = logging.getLogger(__name__)


class _InMemorySubscription:
    def __init__(
        self,
        bus: "InMemoryEventBus",
        pattern: str,
        *,
        payload_type: type[PayloadT],
        queue_size: int,
    ) -> None:
        self._bus = bus
        self.pattern = pattern
        self.queue: asyncio.Queue[Event[Any]] = asyncio.Queue(maxsize=queue_size)
        self.dropped = 0
        self._payload_type = payload_type
        self._adapter: TypeAdapter[PayloadT] = TypeAdapter(payload_type)
        self._active = True

    def offer(self, event: Event[Any]) -> None:
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            self.queue.get_nowait()
            self.dropped += 1
            logger.warning(
                "subscriber for pattern %r is falling behind, dropped event %s "
                "(total dropped: %d)",
                self.pattern,
                event.id,
                self.dropped,
            )
            self.queue.put_nowait(event)

    async def unsubscribe(self) -> None:
        if not self._active:
            return
        self._active = False
        self._bus._remove_subscription(self)

    async def __aenter__(self) -> "_InMemorySubscription":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.unsubscribe()

    def __aiter__(self) -> "_InMemorySubscription":
        return self

    async def __anext__(self) -> Event[Any]:
        while True:
            event = await self.queue.get()
            if self._payload_type is dict:
                return event

            try:
                payload = self._adapter.validate_python(event.payload)
            except Exception:
                logger.warning(
                    "event %s payload did not match %r, skipping",
                    event.id,
                    self._payload_type,
                    exc_info=True,
                )
                continue

            return event.model_copy(update={"payload": payload})


class InMemoryEventBus:
    """An EventBus implementation backed by in-process asyncio queues.

    Useful for local development, tests, and single-process deployments.
    Does not persist events or share state across processes.
    """

    def __init__(self) -> None:
        self._subscriptions: list[_InMemorySubscription] = []

    async def publish(self, event: Event[Any]) -> None:
        for sub in self._subscriptions:
            if matches(sub.pattern, event.event_type):
                sub.offer(event)

    def subscriber_count(self, pattern: str | None = None) -> int:
        if pattern is None:
            return len(self._subscriptions)
        return sum(1 for sub in self._subscriptions if sub.pattern == pattern)

    def subscribe(
        self,
        pattern: str,
        *,
        payload_type: type[PayloadT] = dict,
        queue_size: int = DEFAULT_QUEUE_SIZE,
    ) -> _InMemorySubscription:
        validate_pattern(pattern)
        sub = _InMemorySubscription(
            self, pattern, payload_type=payload_type, queue_size=queue_size
        )
        self._subscriptions.append(sub)
        return sub

    def _remove_subscription(self, sub: _InMemorySubscription) -> None:
        self._subscriptions.remove(sub)
