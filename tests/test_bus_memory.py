import asyncio

import pytest
from pydantic import BaseModel

from agentevents.bus import InMemoryEventBus
from agentevents.models import Event


class ErrorRateSpiked(BaseModel):
    rate: float


async def _collect(bus: InMemoryEventBus, pattern: str, count: int, **kwargs) -> list[Event]:
    results = []
    async with bus.subscribe(pattern, **kwargs) as sub:
        async for event in sub:
            results.append(event)
            if len(results) == count:
                return results
    return results


async def test_subscriber_receives_matching_events() -> None:
    bus = InMemoryEventBus()
    task = asyncio.create_task(_collect(bus, "error_rate.*", 2))
    await asyncio.sleep(0.01)

    await bus.publish(Event(event_type="error_rate.spiked", source="monitor", payload={}))
    await bus.publish(Event(event_type="deploy.started", source="deployer", payload={}))
    await bus.publish(Event(event_type="error_rate.recovered", source="monitor", payload={}))

    results = await asyncio.wait_for(task, timeout=1)
    assert [e.event_type for e in results] == ["error_rate.spiked", "error_rate.recovered"]


async def test_no_subscribers_does_not_raise() -> None:
    bus = InMemoryEventBus()
    await bus.publish(Event(event_type="deploy.started", source="deployer", payload={}))


async def test_multiple_subscribers_each_get_the_event() -> None:
    bus = InMemoryEventBus()
    task_a = asyncio.create_task(_collect(bus, "deploy.*", 1))
    task_b = asyncio.create_task(_collect(bus, "deploy.*", 1))
    await asyncio.sleep(0.01)

    await bus.publish(Event(event_type="deploy.started", source="deployer", payload={}))

    results_a = await asyncio.wait_for(task_a, timeout=1)
    results_b = await asyncio.wait_for(task_b, timeout=1)
    assert results_a[0].event_type == "deploy.started"
    assert results_b[0].event_type == "deploy.started"


async def test_backpressure_drops_oldest() -> None:
    bus = InMemoryEventBus()
    task = asyncio.create_task(_collect(bus, "task.*", 2, queue_size=2))
    await asyncio.sleep(0.01)

    for n in range(5):
        await bus.publish(Event(event_type="task.done", source="worker", payload={"n": n}))

    results = await asyncio.wait_for(task, timeout=1)
    assert [e.payload["n"] for e in results] == [3, 4]


async def test_typed_subscription_coerces_payload() -> None:
    bus = InMemoryEventBus()
    task = asyncio.create_task(
        _collect(bus, "error_rate.*", 1, payload_type=ErrorRateSpiked)
    )
    await asyncio.sleep(0.01)

    await bus.publish(
        Event(event_type="error_rate.spiked", source="monitor", payload={"rate": 0.9})
    )

    results = await asyncio.wait_for(task, timeout=1)
    assert isinstance(results[0].payload, ErrorRateSpiked)
    assert results[0].payload.rate == 0.9


async def test_typed_subscription_skips_invalid_payload() -> None:
    bus = InMemoryEventBus()
    task = asyncio.create_task(
        _collect(bus, "error_rate.*", 1, payload_type=ErrorRateSpiked)
    )
    await asyncio.sleep(0.01)

    await bus.publish(
        Event(event_type="error_rate.spiked", source="monitor", payload={"rate": "bad"})
    )
    await bus.publish(
        Event(event_type="error_rate.spiked", source="monitor", payload={"rate": 0.4})
    )

    results = await asyncio.wait_for(task, timeout=1)
    assert results[0].payload.rate == 0.4


async def test_subscription_cleaned_up_on_break() -> None:
    # __aexit__ runs synchronously on block exit (return, break, or
    # exception), so cleanup is guaranteed immediately — no reliance on
    # generator GC timing.
    bus = InMemoryEventBus()

    async def consume_one():
        async with bus.subscribe("deploy.*") as sub:
            async for _ in sub:
                break

    task = asyncio.create_task(consume_one())
    await asyncio.sleep(0.01)
    assert len(bus._subscriptions) == 1

    await bus.publish(Event(event_type="deploy.started", source="deployer", payload={}))
    await asyncio.wait_for(task, timeout=1)
    assert bus._subscriptions == []


async def test_subscription_cleaned_up_on_cancel() -> None:
    bus = InMemoryEventBus()

    async def consume_forever():
        async with bus.subscribe("deploy.*") as sub:
            async for _ in sub:
                pass

    task = asyncio.create_task(consume_forever())
    await asyncio.sleep(0.01)
    assert len(bus._subscriptions) == 1

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert bus._subscriptions == []


async def test_unsubscribe_is_idempotent() -> None:
    bus = InMemoryEventBus()
    sub = bus.subscribe("deploy.*")
    async with sub:
        pass
    await sub.unsubscribe()
    assert bus._subscriptions == []


async def test_dropped_count_is_visible_on_subscription() -> None:
    bus = InMemoryEventBus()
    async with bus.subscribe("task.*", queue_size=2) as sub:
        for n in range(5):
            await bus.publish(Event(event_type="task.done", source="worker", payload={"n": n}))
        assert sub.dropped == 3
