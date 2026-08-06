import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from pydantic import TypeAdapter

from agentevents.bus.protocol import DEFAULT_QUEUE_SIZE
from agentevents.matching import matches
from agentevents.models import Event, PayloadT

logger = logging.getLogger(__name__)


class _Subscription:
    def __init__(self, pattern: str, queue_size: int) -> None:
        self.pattern = pattern
        self.queue: asyncio.Queue[Event[Any]] = asyncio.Queue(maxsize=queue_size)
        self.dropped = 0

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


class InMemoryEventBus:
    """An EventBus implementation backed by in-process asyncio queues.

    Useful for local development, tests, and single-process deployments.
    Does not persist events or share state across processes.
    """

    def __init__(self) -> None:
        self._subscriptions: list[_Subscription] = []

    async def publish(self, event: Event[Any]) -> None:
        for sub in self._subscriptions:
            if matches(sub.pattern, event.event_type):
                sub.offer(event)

    async def subscribe(
        self,
        pattern: str,
        *,
        payload_type: type[PayloadT] = dict,
        queue_size: int = DEFAULT_QUEUE_SIZE,
    ) -> AsyncIterator[Event[PayloadT]]:
        sub = _Subscription(pattern, queue_size)
        self._subscriptions.append(sub)
        adapter: TypeAdapter[PayloadT] = TypeAdapter(payload_type)

        try:
            while True:
                event = await sub.queue.get()
                if payload_type is dict:
                    yield event
                    continue

                try:
                    payload = adapter.validate_python(event.payload)
                except Exception:
                    logger.warning(
                        "event %s payload did not match %r, skipping",
                        event.id,
                        payload_type,
                        exc_info=True,
                    )
                    continue

                yield event.model_copy(update={"payload": payload})
        finally:
            self._subscriptions.remove(sub)
