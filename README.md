# agentevents

[![CI](https://github.com/Charlesreilly0/agentevents/actions/workflows/ci.yml/badge.svg)](https://github.com/Charlesreilly0/agentevents/actions/workflows/ci.yml)

A Python library for event-driven communication between agents. Agents publish events to a bus and other agents subscribe to the event types they care about. This is a complement to request/response protocols like A2A, for cases where an agent needs to react to something it did not directly ask for.

## Installation

This project uses [uv](https://github.com/astral-sh/uv).

```
uv add agentevents
```

## Quickstart

```python
import asyncio

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
            return


async def main():
    task = asyncio.create_task(rollback_agent())
    await asyncio.sleep(0.05)
    await monitor()
    await task


asyncio.run(main())
```

## Documentation

- [API reference](docs/api.md) — `Event`, `EventBus`, `InMemoryEventBus`, `RedisEventBus`, pattern matching, typed subscriptions, backpressure, and exceptions.
- [Implementing a new EventBus backend](docs/backend-guide.md)
- [Runnable examples](examples/)
- [Changelog](CHANGELOG.md)

The same documentation is also published to the [GitHub wiki](https://github.com/Charlesreilly0/agentevents/wiki) for browsing; `docs/` in this repository is the source of truth.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, running tests, and running the CLI.
