# Implementing a new EventBus backend

`agentevents` ships two backends: `InMemoryEventBus` (single process, `src/agentevents/bus/memory.py`) and `RedisEventBus` (Redis Pub/Sub, `src/agentevents/bus/redis.py`). A new backend — NATS, Kafka, Redis Streams, a cloud pub/sub service — needs to satisfy the `EventBus` and `Subscription` protocols in `src/agentevents/bus/protocol.py`. Read both existing implementations side by side before starting; they're deliberately similar, and the diff between them is exactly the part that's backend-specific.

## What's reusable as-is

The two existing backends share almost the entire `_Subscription` implementation verbatim:

- A bounded `asyncio.Queue[Event[Any]]` per subscription, with an `offer()` method that does drop-oldest backpressure (`put_nowait`, and on `QueueFull`, evict the oldest item, increment a `dropped` counter, log a warning, then enqueue the new one). This is transport-independent — copy it.
- `__anext__` pulling off that local queue and, if `payload_type` isn't `dict`, validating/coercing the payload via `pydantic.TypeAdapter`, logging and skipping (not raising) on a mismatch so one malformed event doesn't kill the subscriber loop.
- `__aenter__`/`__aiter__` returning `Self` (not a quoted class name — see `from __future__ import annotations` at the top of both files), and `__aexit__` calling `unsubscribe()`. This is what makes `async with bus.subscribe(...) as sub: ...` deterministic: `__aexit__` is guaranteed to run synchronously on block exit (return, `break`, or exception), unlike relying on an async generator's `finally`, which only runs on garbage collection — a bug we hit and fixed during this library's own development. Don't reintroduce it by returning a bare async generator from `subscribe()`.
- `unsubscribe()` being idempotent (`if not self._active: return`), and `subscriber_count()`'s implementation (count `self._subscriptions`, optionally filtered by exact pattern string — not a wildcard match).
- `validate_pattern(pattern)` at the top of `subscribe()`, before constructing anything. Every backend must call this; it's what makes a malformed pattern (`"deploy.>.rollback"`, an empty segment, uppercase) fail loudly at subscribe time instead of silently matching nothing forever.

## What's actually backend-specific

Only one thing genuinely differs between backends: **how an event gets from `publish()` into a subscription's `offer()`**. Compare the two:

- `InMemoryEventBus.publish()` just loops over `self._subscriptions` in-process and calls `matches(sub.pattern, event.event_type)` / `sub.offer(event)` directly — no network, no serialization.
- `RedisEventBus.publish()` serializes the `Event` to JSON and does `PUBLISH` on a shared channel; a single background listener task (`_listen()`, started lazily on first subscription via `_ensure_listener()`) reads every message off that channel, deserializes it, and does the same `matches()` / `offer()` fan-out to every local subscription. Every subscriber process receives every published event and filters client-side, because Redis Pub/Sub has no `*`/`>` wildcard concept of its own.

A new backend's job is to answer: **does the underlying transport support server-side subject/topic wildcards matching our `*`/`>` grammar, or does it need client-side filtering like Redis?**

- If yes (NATS subjects are the closest native match — `*` for one token, `>` for trailing tokens, nearly identical to our grammar), you may be able to subscribe per-pattern directly against the transport instead of one shared channel + local `matches()` calls. This is more efficient (the broker filters before sending you anything) but means `subscribe()` needs to do real I/O (open a transport-level subscription), which `InMemoryEventBus.subscribe()` doesn't — see the next section.
- If no (Kafka, Redis Streams, most cloud pub/sub), follow the `RedisEventBus` shape: one shared topic/stream, one listener loop, client-side `matches()` filtering into local queues.

## The subscribe() I/O problem

`EventBus.subscribe()` is a **synchronous** method in the protocol (it has to be, so it can be called before any `await`). But most real transports need async I/O to actually register a subscription (open a connection, call `SUBSCRIBE`). `RedisEventBus` solves this by making `subscribe()` synchronous and cheap (just append to a local list) and deferring the real connection work to `_ensure_listener()`, called from `Subscription.__aenter__` and `__anext__` — i.e., the first time the subscription is actually used inside an `async with` block, not when `subscribe()` is called. Follow this pattern rather than trying to make `subscribe()` itself async (it can't be, without breaking the protocol).

## Error handling

Wrap the underlying client library's connection/transport errors in `EventBusConnectionError` (`src/agentevents/exceptions.py`) at the points where your backend actually talks to the network — see `RedisEventBus._ensure_listener()` and `.publish()` for the pattern (`except <library>Error as exc: raise EventBusConnectionError(...) from exc`). This is the whole point of having a library-specific exception: code written against `EventBus` shouldn't need to import a specific backend's exception types to handle "the bus is unreachable."

## Testing a new backend

Mirror the existing test layout:

- `tests/unit/` — if any part of your backend can be tested without the real transport (e.g., a pure serialization/deserialization round-trip), it belongs here.
- `tests/integration/`, marked `@pytest.mark.integration`, using [testcontainers](https://testcontainers.com/) if a containerized version of your backend exists (see `tests/integration/conftest.py`'s `redis_url` fixture for the pattern). At minimum, mirror `tests/integration/test_bus_redis.py`'s coverage: publish/subscribe within one bus instance, wildcard filtering, two separate bus instances communicating (the test that actually proves cross-process behavior), typed payload coercion, backpressure/drop-oldest, deterministic cleanup on `break`, `subscriber_count`, invalid pattern rejection, and connection-error wrapping against an unreachable server.

Open an issue or discussion making the case for a specific transport before writing a full backend — backends aren't added speculatively here, so a concrete reason (a real workload that needs replay, or a team already standardized on a given broker) is worth more than "more options."
