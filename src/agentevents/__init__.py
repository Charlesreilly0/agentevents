from __future__ import annotations

from agentevents.bus import EventBus, InMemoryEventBus, RedisEventBus, Subscription
from agentevents.exceptions import (
    AgentEventsError,
    EventBusConnectionError,
    InvalidEventTypeError,
)
from agentevents.matching import matches
from agentevents.models import Event

__all__ = [
    "AgentEventsError",
    "Event",
    "EventBus",
    "EventBusConnectionError",
    "InMemoryEventBus",
    "InvalidEventTypeError",
    "RedisEventBus",
    "Subscription",
    "matches",
]


def main() -> None:
    print("Hello from agentevents!")
