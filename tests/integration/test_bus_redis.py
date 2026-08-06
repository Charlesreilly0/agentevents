import asyncio

import pytest
from pydantic import BaseModel

from agentevents.bus import RedisEventBus
from agentevents.exceptions import EventBusConnectionError, InvalidEventTypeError
from agentevents.models import Event

pytestmark = pytest.mark.integration


class ErrorRateSpiked(BaseModel):
    rate: float


async def _collect(bus: RedisEventBus, pattern: str, count: int, **kwargs) -> list[Event]:
    results = []
    async with bus.subscribe(pattern, **kwargs) as sub:
        async for event in sub:
            results.append(event)
            if len(results) == count:
                return results
    return results


@pytest.fixture
async def bus(redis_url: str):
    b = RedisEventBus(redis_url, channel=f"test:{id(object())}")
    yield b
    await b.aclose()


async def test_publish_and_subscribe_within_one_bus(bus: RedisEventBus) -> None:
    task = asyncio.create_task(_collect(bus, "error_rate.*", 1))
    await asyncio.sleep(0.2)

    await bus.publish(Event(event_type="error_rate.spiked", source="monitor", payload={}))

    results = await asyncio.wait_for(task, timeout=5)
    assert results[0].event_type == "error_rate.spiked"


async def test_wildcard_filters_out_non_matching_events(bus: RedisEventBus) -> None:
    task = asyncio.create_task(_collect(bus, "error_rate.*", 1))
    await asyncio.sleep(0.2)

    await bus.publish(Event(event_type="deploy.started", source="deployer", payload={}))
    await bus.publish(Event(event_type="error_rate.spiked", source="monitor", payload={}))

    results = await asyncio.wait_for(task, timeout=5)
    assert results[0].event_type == "error_rate.spiked"


async def test_two_separate_bus_instances_communicate(redis_url: str) -> None:
    # Simulates two different processes/agents: one publishes on its own
    # RedisEventBus instance, the other subscribes on a different
    # instance pointed at the same Redis server and channel.
    channel = f"test:{id(object())}"
    publisher_bus = RedisEventBus(redis_url, channel=channel)
    subscriber_bus = RedisEventBus(redis_url, channel=channel)
    try:
        task = asyncio.create_task(_collect(subscriber_bus, "task.*", 1))
        await asyncio.sleep(0.2)

        await publisher_bus.publish(
            Event(event_type="task.completed", source="worker-agent", payload={"ok": True})
        )

        results = await asyncio.wait_for(task, timeout=5)
        assert results[0].event_type == "task.completed"
        assert results[0].payload == {"ok": True}
    finally:
        await publisher_bus.aclose()
        await subscriber_bus.aclose()


async def test_typed_subscription_coerces_payload(bus: RedisEventBus) -> None:
    task = asyncio.create_task(
        _collect(bus, "error_rate.*", 1, payload_type=ErrorRateSpiked)
    )
    await asyncio.sleep(0.2)

    await bus.publish(
        Event(event_type="error_rate.spiked", source="monitor", payload={"rate": 0.75})
    )

    results = await asyncio.wait_for(task, timeout=5)
    assert isinstance(results[0].payload, ErrorRateSpiked)
    assert results[0].payload.rate == 0.75


async def test_backpressure_drops_oldest(bus: RedisEventBus) -> None:
    # Registers the subscription and starts the listener without draining
    # its queue, so all 5 publishes are offered to it before anything is
    # read back. Otherwise, over a real network, the consumer can drain
    # the queue between publishes and no backpressure is ever exercised.
    async with bus.subscribe("task.*", queue_size=2) as sub:
        await asyncio.sleep(0.2)

        for n in range(5):
            await bus.publish(Event(event_type="task.done", source="worker", payload={"n": n}))

        await asyncio.sleep(0.2)

        results = [await anext(sub), await anext(sub)]
        assert [e.payload["n"] for e in results] == [3, 4]


async def test_subscription_cleaned_up_on_break(bus: RedisEventBus) -> None:
    async def consume_one():
        async with bus.subscribe("deploy.*") as sub:
            async for _ in sub:
                break

    task = asyncio.create_task(consume_one())
    await asyncio.sleep(0.2)
    assert bus.subscriber_count() == 1

    await bus.publish(Event(event_type="deploy.started", source="deployer", payload={}))
    await asyncio.wait_for(task, timeout=5)
    assert bus.subscriber_count() == 0


async def test_subscriber_count_by_pattern(bus: RedisEventBus) -> None:
    async with (
        bus.subscribe("deploy.*") as sub_a,
        bus.subscribe("deploy.*") as sub_b,
        bus.subscribe("task.*") as sub_c,
    ):
        await asyncio.sleep(0.2)
        assert bus.subscriber_count() == 3
        assert bus.subscriber_count("deploy.*") == 2
        assert bus.subscriber_count("task.*") == 1


async def test_subscribe_rejects_invalid_pattern(bus: RedisEventBus) -> None:
    with pytest.raises(InvalidEventTypeError):
        bus.subscribe("deploy.>.rollback")
    assert bus.subscriber_count() == 0


async def test_unreachable_redis_raises_connection_error() -> None:
    bus = RedisEventBus("redis://localhost:1/0")
    try:
        with pytest.raises(EventBusConnectionError):
            async with bus.subscribe("deploy.*"):
                pass
    finally:
        await bus.aclose()
