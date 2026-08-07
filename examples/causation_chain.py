"""
Tracing a multi-agent cascade with correlation_id and causation_id.

Three agents react to each other in sequence, entirely through an
InMemoryEventBus, with no agent calling another directly:

    monitoring_agent   -> publishes error_rate.spiked
    rollback_agent      -> reacts, publishes rollback.triggered
    notification_agent  -> reacts, publishes notification.sent

Every event in the chain shares one correlation_id (set on the first
event and carried forward by each agent that reacts to it), and each
event's causation_id points at the id of the event that triggered it.
That's what lets you reconstruct the whole cascade afterward, which
this example does at the end by walking the chain from the last event
back to the first via causation_id.

This example doesn't use an LLM (see examples/pydantic_ai_incident_response.py
for that) since the thing being demonstrated is the event model's chain
tracing, not agent reasoning.

Run with:
    uv run python examples/causation_chain.py
"""

import asyncio

from agentevents import Event, InMemoryEventBus


async def monitoring_agent(bus: InMemoryEventBus) -> None:
    """Detects a spike and starts a new correlation chain."""
    event = Event(
        event_type="error_rate.spiked",
        source="monitoring-agent",
        payload={"rate": 0.42, "threshold": 0.1},
        # No correlation_id given: this event starts a new one, defaulting
        # to its own id (see main(), which reads it back off the event).
    )
    await bus.publish(event)


async def rollback_agent(bus: InMemoryEventBus) -> None:
    """Reacts to a spike by triggering a rollback, in the same chain."""
    async with bus.subscribe("error_rate.*") as sub:
        async for spike_event in sub:
            rollback_event = Event(
                event_type="rollback.triggered",
                source="rollback-agent",
                payload={"reason": f"reacting to {spike_event.event_type}"},
                correlation_id=spike_event.correlation_id or spike_event.id,
                causation_id=spike_event.id,
            )
            await bus.publish(rollback_event)
            return


async def notification_agent(bus: InMemoryEventBus) -> None:
    """Reacts to a rollback by notifying, in the same chain."""
    async with bus.subscribe("rollback.*") as sub:
        async for rollback_event in sub:
            notification_event = Event(
                event_type="notification.sent",
                source="notification-agent",
                payload={"message": f"rollback triggered: {rollback_event.payload['reason']}"},
                correlation_id=rollback_event.correlation_id,
                causation_id=rollback_event.id,
            )
            await bus.publish(notification_event)
            return


async def audit_log(bus: InMemoryEventBus, expected_count: int) -> list[Event]:
    """Not a participant in the cascade: just observes every event on the
    bus, to reconstruct and print the chain afterward."""
    events: list[Event] = []
    async with bus.subscribe(">") as sub:
        async for event in sub:
            events.append(event)
            if len(events) == expected_count:
                return events
    return events


def print_chain(events: list[Event]) -> None:
    # The root is the one event in the batch with no causation_id: nothing
    # caused it, it started the chain.
    root = next(event for event in events if event.causation_id is None)

    print(f"\ncorrelation_id: {root.correlation_id or root.id}")
    current: Event | None = root
    depth = 0
    while current is not None:
        print(f"{'  ' * depth}-> {current.event_type} (from {current.source}): {current.payload}")
        current = next((event for event in events if event.causation_id == current.id), None)
        depth += 1


async def main() -> None:
    bus = InMemoryEventBus()

    audit_task = asyncio.create_task(audit_log(bus, expected_count=3))
    rollback_task = asyncio.create_task(rollback_agent(bus))
    notification_task = asyncio.create_task(notification_agent(bus))
    await asyncio.sleep(0.05)

    await monitoring_agent(bus)

    await asyncio.wait_for(rollback_task, timeout=1)
    await asyncio.wait_for(notification_task, timeout=1)
    events = await asyncio.wait_for(audit_task, timeout=1)

    print_chain(events)


if __name__ == "__main__":
    asyncio.run(main())
