"""
Two Pydantic AI agents coordinating through agentevents instead of calling
each other directly.

A monitoring agent has a tool that publishes an `error_rate.spiked` event
when it decides a metric warrants attention. A rollback agent subscribes to
that event type and reacts, without the monitoring agent knowing the
rollback agent exists.

This uses pydantic_ai.models.test.TestModel so the example runs with no API
key. TestModel doesn't do real inference: it calls the available tool and
fills its arguments with type-appropriate placeholder values (0.0 for
floats), so the published event's rate/threshold will be 0.0, not values
parsed from the prompt. Swap TestModel for a real model (e.g.
`Agent("openai:gpt-4o", ...)`, with the corresponding API key set) to see
the agent actually decide the values from its instructions.

Run with:
    uv run --group examples python examples/pydantic_ai_incident_response.py
"""

import asyncio
from dataclasses import dataclass

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.test import TestModel

from agentevents import Event, InMemoryEventBus


class ErrorRateSpiked(BaseModel):
    rate: float
    threshold: float


@dataclass
class MonitoringDeps:
    bus: InMemoryEventBus
    source: str


monitoring_agent = Agent(
    TestModel(),
    deps_type=MonitoringDeps,
    system_prompt=(
        "You watch service error rates. When asked to report a spike, "
        "call report_error_rate_spike with the rate and threshold."
    ),
)


@monitoring_agent.tool
async def report_error_rate_spike(
    ctx: RunContext[MonitoringDeps], rate: float, threshold: float
) -> str:
    """Publish an error_rate.spiked event for other agents to react to."""
    event = Event[ErrorRateSpiked](
        event_type="error_rate.spiked",
        source=ctx.deps.source,
        payload=ErrorRateSpiked(rate=rate, threshold=threshold),
    )
    await ctx.deps.bus.publish(event)
    return f"published error_rate.spiked (rate={rate}, threshold={threshold})"


async def rollback_agent(bus: InMemoryEventBus) -> None:
    """A separate agent that only knows about the event, not the publisher."""
    async with bus.subscribe("error_rate.*", payload_type=ErrorRateSpiked) as sub:
        async for event in sub:
            print(
                f"[rollback_agent] received {event.event_type} from {event.source}: "
                f"rate={event.payload.rate}, threshold={event.payload.threshold}"
            )
            print("[rollback_agent] triggering rollback...")
            return


async def main() -> None:
    bus = InMemoryEventBus()

    # Start the rollback agent listening before the monitoring agent runs,
    # so it's registered in time to receive the event.
    rollback_task = asyncio.create_task(rollback_agent(bus))
    await asyncio.sleep(0.05)

    deps = MonitoringDeps(bus=bus, source="monitoring-agent")
    result = await monitoring_agent.run(
        "Error rate has spiked to 0.42 against a threshold of 0.1. Report it.",
        deps=deps,
    )
    print(f"[monitoring_agent] {result.output}")

    await asyncio.wait_for(rollback_task, timeout=1)


if __name__ == "__main__":
    asyncio.run(main())
