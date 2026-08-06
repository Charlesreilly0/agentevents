import asyncio

import pytest
from pydantic import BaseModel

from agentevents.bus import InMemoryEventBus
from agentevents.exceptions import InvalidEventTypeError
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
    assert bus.subscriber_count() == 1

    await bus.publish(Event(event_type="deploy.started", source="deployer", payload={}))
    await asyncio.wait_for(task, timeout=1)
    assert bus.subscriber_count() == 0


async def test_subscription_cleaned_up_on_cancel() -> None:
    bus = InMemoryEventBus()

    async def consume_forever():
        async with bus.subscribe("deploy.*") as sub:
            async for _ in sub:
                pass

    task = asyncio.create_task(consume_forever())
    await asyncio.sleep(0.01)
    assert bus.subscriber_count() == 1

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert bus.subscriber_count() == 0


async def test_unsubscribe_is_idempotent() -> None:
    bus = InMemoryEventBus()
    sub = bus.subscribe("deploy.*")
    async with sub:
        pass
    await sub.unsubscribe()
    assert bus.subscriber_count() == 0


async def test_dropped_count_is_visible_on_subscription() -> None:
    bus = InMemoryEventBus()
    async with bus.subscribe("task.*", queue_size=2) as sub:
        for n in range(5):
            await bus.publish(Event(event_type="task.done", source="worker", payload={"n": n}))
        assert sub.dropped == 3


async def test_subscriber_count_total_and_by_pattern() -> None:
    bus = InMemoryEventBus()
    assert bus.subscriber_count() == 0

    async with bus.subscribe("deploy.*") as sub_a, bus.subscribe("deploy.*") as sub_b, bus.subscribe("task.*") as sub_c:
        assert bus.subscriber_count() == 3
        assert bus.subscriber_count("deploy.*") == 2
        assert bus.subscriber_count("task.*") == 1
        assert bus.subscriber_count("nothing.matches") == 0

    assert bus.subscriber_count() == 0


async def test_many_concurrent_publishers_and_subscribers() -> None:
    bus = InMemoryEventBus()
    num_subscribers = 10
    num_publishers = 5
    events_per_publisher = 20
    total_events = num_publishers * events_per_publisher

    tasks = [
        asyncio.create_task(_collect(bus, "load.*", total_events))
        for _ in range(num_subscribers)
    ]
    await asyncio.sleep(0.01)
    assert bus.subscriber_count() == num_subscribers

    async def publish_batch(publisher_id: int) -> None:
        for n in range(events_per_publisher):
            await bus.publish(
                Event(
                    event_type="load.tick",
                    source=f"publisher-{publisher_id}",
                    payload={"n": n},
                )
            )

    await asyncio.gather(*(publish_batch(i) for i in range(num_publishers)))

    results = await asyncio.gather(*(asyncio.wait_for(t, timeout=2) for t in tasks))
    for subscriber_results in results:
        assert len(subscriber_results) == total_events

    assert bus.subscriber_count() == 0


async def test_subscriber_that_raises_still_cleans_up() -> None:
    bus = InMemoryEventBus()

    class BoomError(Exception):
        pass

    async def consume_and_raise():
        async with bus.subscribe("deploy.*") as sub:
            async for _ in sub:
                raise BoomError

    task = asyncio.create_task(consume_and_raise())
    await asyncio.sleep(0.01)
    assert bus.subscriber_count() == 1

    await bus.publish(Event(event_type="deploy.started", source="deployer", payload={}))

    with pytest.raises(BoomError):
        await asyncio.wait_for(task, timeout=1)

    assert bus.subscriber_count() == 0


async def test_one_raising_subscriber_does_not_affect_others() -> None:
    bus = InMemoryEventBus()

    class BoomError(Exception):
        pass

    async def bad_subscriber():
        async with bus.subscribe("deploy.*") as sub:
            async for _ in sub:
                raise BoomError

    good_task = asyncio.create_task(_collect(bus, "deploy.*", 1))
    bad_task = asyncio.create_task(bad_subscriber())
    await asyncio.sleep(0.01)
    assert bus.subscriber_count() == 2

    await bus.publish(Event(event_type="deploy.started", source="deployer", payload={}))

    with pytest.raises(BoomError):
        await asyncio.wait_for(bad_task, timeout=1)

    good_results = await asyncio.wait_for(good_task, timeout=1)
    assert good_results[0].event_type == "deploy.started"
    assert bus.subscriber_count() == 0


async def test_subscribe_rejects_invalid_pattern() -> None:
    bus = InMemoryEventBus()
    with pytest.raises(InvalidEventTypeError):
        bus.subscribe("deploy.>.rollback")
    assert bus.subscriber_count() == 0
