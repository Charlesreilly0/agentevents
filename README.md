# agentevents

A Python library for event-driven communication between agents. Agents publish events to a bus and other agents subscribe to the event types they care about. This is a complement to request/response protocols like A2A, for cases where an agent needs to react to something it did not directly ask for.

## Installation

This project uses [uv](https://github.com/astral-sh/uv).

```
uv add agentevents
```

## Core concepts

### Event

An `Event` is the unit of communication. It has a routing key (`event_type`), an identity, a source, a timestamp, and a payload.

```python
from agentevents import Event

event = Event(
    event_type="error_rate.spiked",
    source="monitoring-agent",
    payload={"rate": 0.42},
)
```

Fields:

- `id`: a UUID generated automatically.
- `event_type`: a lowercase, dot-namespaced string with at least two segments, for example `error_rate.spiked` or `deploy.prod.rollback.triggered`. This is validated on construction.
- `source`: the identifier of the agent that emitted the event.
- `timestamp`: UTC time, generated automatically.
- `correlation_id`: optional. Groups events that belong to the same logical run or workflow.
- `causation_id`: optional. Points to the id of the event that directly caused this one.
- `payload`: required. The event-specific data.
- `metadata`: an open dict for protocol or transport level concerns, such as schema version or delivery hints.

`Event` is generic over the payload type. By default `payload` is a plain dict. You can also give it a Pydantic model for validation:

```python
from pydantic import BaseModel

class ErrorRateSpiked(BaseModel):
    rate: float
    threshold: float

event = Event[ErrorRateSpiked](
    event_type="error_rate.spiked",
    source="monitoring-agent",
    payload=ErrorRateSpiked(rate=0.42, threshold=0.1),
)
```

### EventBus

`EventBus` is a protocol with two operations: `publish` and `subscribe`. Two implementations are provided:

- `InMemoryEventBus`, backed by in-process asyncio queues. Meant for local development, testing, and single-process use. Does not persist events or share state across processes.
- `RedisEventBus`, backed by Redis Pub/Sub. Multiple bus instances, in the same process or different ones, that point at the same Redis server and channel form one shared bus. Use this when agents run in separate processes or on separate machines.

```python
from agentevents import Event, InMemoryEventBus

bus = InMemoryEventBus()

async def monitor():
    await bus.publish(
        Event(event_type="error_rate.spiked", source="monitor", payload={"rate": 0.9})
    )

async def rollback_agent():
    async with bus.subscribe("error_rate.*") as sub:
        async for event in sub:
            print(event.event_type, event.payload)
```

`subscribe` returns a `Subscription`. Use it as an async context manager. This guarantees the subscription is deregistered from the bus the moment the block exits, whether that is by falling through, by `break`, or by an exception. Do not iterate a `Subscription` outside of an `async with` block, since cleanup then depends on garbage collection timing rather than running immediately.

### RedisEventBus

`RedisEventBus` publishes each event as JSON to a single Redis channel. Every subscriber process receives every published message and filters it locally using the same pattern matching as `InMemoryEventBus`. This keeps the `*` and `>` wildcard grammar and the drop-oldest backpressure behavior identical across both implementations, at the cost of sending every event over the wire to every subscribed process.

```python
from agentevents import Event, RedisEventBus

bus = RedisEventBus("redis://localhost:6379/0")

async def monitor():
    await bus.publish(
        Event(event_type="error_rate.spiked", source="monitor", payload={"rate": 0.9})
    )

async def rollback_agent():
    async with bus.subscribe("error_rate.*") as sub:
        async for event in sub:
            print(event.event_type, event.payload)

await bus.aclose()  # closes the shared listener connection when done
```

Redis Pub/Sub is fire-and-forget. Events published before a subscriber's listener has started, or while it is disconnected, are not delivered or replayed. Call `bus.aclose()` when you are done with a bus instance to close its Redis connection and stop its background listener task.

### Pattern matching

`subscribe` takes a pattern instead of an exact event type. Patterns are matched segment by segment against dot-namespaced event types.

- A literal segment must match exactly.
- `*` matches exactly one segment.
- `>` matches one or more trailing segments, and must be the last segment in the pattern.

Examples:

| Pattern | Matches | Does not match |
|---|---|---|
| `error_rate.*` | `error_rate.spiked` | `deploy.started` |
| `*.spiked` | `error_rate.spiked` | `error_rate.recovered` |
| `deploy.>` | `deploy.started`, `deploy.prod.rollback` | `rollback.started` |

### Typed subscriptions

Pass `payload_type` to `subscribe` to validate and coerce incoming payloads into a specific model. Events whose payload does not match are logged and skipped, not raised, so one malformed event does not stop the subscriber loop.

```python
async with bus.subscribe("error_rate.*", payload_type=ErrorRateSpiked) as sub:
    async for event in sub:
        print(event.payload.rate)
```

### Backpressure

Each subscription has a bounded queue, sized by `queue_size` (default 100). If a subscriber falls behind the rate of publishing, the oldest buffered event is dropped to make room for the newest one. `publish` never blocks on a slow subscriber. The number of dropped events for a subscription is available on `sub.dropped`.

### Introspection

`bus.subscriber_count()` returns the number of active subscriptions. Pass a pattern to count only subscriptions registered with that exact pattern string.

```python
bus.subscriber_count()              # total active subscriptions
bus.subscriber_count("deploy.*")    # only subscriptions registered with this pattern
```

## Development

Install dependencies:

```
uv sync
```

Run unit tests. These do not need Docker and run by default:

```
uv run pytest
```

Run integration tests. These use [testcontainers](https://testcontainers.com/) to start a real Redis in Docker, and are excluded from the default run since they need Docker available:

```
uv run pytest -m integration
```

If Docker is provided by Colima or another non-default runtime, testcontainers' cleanup container (Ryuk) can fail to start because of how its socket is mounted. If integration tests fail with a Docker mount error, disable Ryuk and clean up containers manually instead:

```
TESTCONTAINERS_RYUK_DISABLED=true uv run pytest -m integration
```

Run the CLI entry point:

```
uv run agentevents
```
