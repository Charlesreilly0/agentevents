import asyncio
import logging
from types import TracebackType
from typing import Any

import redis.asyncio as redis_asyncio
import redis.exceptions as redis_exceptions
from pydantic import TypeAdapter

from agentevents.bus.protocol import DEFAULT_QUEUE_SIZE
from agentevents.exceptions import EventBusConnectionError
from agentevents.matching import matches, validate_pattern
from agentevents.models import Event, PayloadT

logger = logging.getLogger(__name__)

DEFAULT_CHANNEL = "agentevents:events"


class _RedisSubscription:
    def __init__(
        self,
        bus: "RedisEventBus",
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

    async def __aenter__(self) -> "_RedisSubscription":
        await self._bus._ensure_listener()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.unsubscribe()

    def __aiter__(self) -> "_RedisSubscription":
        return self

    async def __anext__(self) -> Event[Any]:
        await self._bus._ensure_listener()
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


class RedisEventBus:
    """An EventBus implementation backed by Redis Pub/Sub.

    All instances (in this process or others) that share a Redis server
    and channel name form one bus: publish() PUBLISHes the event as JSON
    to a single shared channel, and each subscribe() filters the channel's
    messages locally using the same */> pattern grammar as
    InMemoryEventBus. This trades some wire traffic (every subscriber
    process receives every published event) for correct wildcard
    matching and consistent drop-oldest backpressure semantics.

    Redis Pub/Sub is fire-and-forget: messages published before a
    subscriber's listener has started, or while it is disconnected, are
    not delivered or replayed.

    The background listener that reads from Redis and fans out to local
    subscriptions is started lazily, on first use of a Subscription
    (entering its `async with` block or iterating it), and is shared by
    all subscriptions on this bus instance.
    """

    def __init__(self, redis_url: str, *, channel: str = DEFAULT_CHANNEL) -> None:
        self._redis_url = redis_url
        self._channel = channel
        self._subscriptions: list[_RedisSubscription] = []
        self._client: redis_asyncio.Redis | None = None
        self._pubsub: Any = None
        self._listener_task: asyncio.Task[None] | None = None
        self._listener_lock = asyncio.Lock()

    async def _ensure_listener(self) -> None:
        if self._listener_task is not None:
            return
        async with self._listener_lock:
            if self._listener_task is not None:
                return
            client = redis_asyncio.from_url(self._redis_url)
            pubsub = client.pubsub()
            try:
                await pubsub.subscribe(self._channel)
            except redis_exceptions.RedisError as exc:
                await client.aclose()
                raise EventBusConnectionError(
                    f"could not connect to Redis at {self._redis_url!r}"
                ) from exc
            self._client = client
            self._pubsub = pubsub
            self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        assert self._pubsub is not None
        async for message in self._pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                event: Event[Any] = Event.model_validate_json(message["data"])
            except Exception:
                logger.warning(
                    "received malformed event on channel %r, skipping",
                    self._channel,
                    exc_info=True,
                )
                continue

            for sub in self._subscriptions:
                if matches(sub.pattern, event.event_type):
                    sub.offer(event)

    async def publish(self, event: Event[Any]) -> None:
        if self._client is None:
            client = redis_asyncio.from_url(self._redis_url)
            try:
                await client.publish(self._channel, event.model_dump_json())
            except redis_exceptions.RedisError as exc:
                raise EventBusConnectionError(
                    f"could not reach Redis at {self._redis_url!r}"
                ) from exc
            finally:
                await client.aclose()
        else:
            try:
                await self._client.publish(self._channel, event.model_dump_json())
            except redis_exceptions.RedisError as exc:
                raise EventBusConnectionError(
                    f"could not reach Redis at {self._redis_url!r}"
                ) from exc

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
    ) -> _RedisSubscription:
        validate_pattern(pattern)
        sub = _RedisSubscription(self, pattern, payload_type=payload_type, queue_size=queue_size)
        self._subscriptions.append(sub)
        return sub

    def _remove_subscription(self, sub: _RedisSubscription) -> None:
        if sub in self._subscriptions:
            self._subscriptions.remove(sub)

    async def aclose(self) -> None:
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._pubsub is not None:
            await self._pubsub.unsubscribe(self._channel)
            await self._pubsub.aclose()
            self._pubsub = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None
