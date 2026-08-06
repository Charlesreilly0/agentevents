from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from agentevents.exceptions import InvalidEventTypeError

EVENT_TYPE_PATTERN = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")

PayloadT = TypeVar("PayloadT", default=dict[str, Any])


class Event(BaseModel, Generic[PayloadT]):
    """
    An event emitted by an agent for other agents to consume.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique identifier for this event.")

    event_type: str = Field(
        description="Lowercase, dot-namespaced routing key, e.g. 'error_rate.spiked'."
    )

    source: str = Field(description="Identifier of the agent that emitted this event.")

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC time the event was created.",
    )

    correlation_id: UUID | None = Field(
        default=None,
        description="Groups events that belong to the same logical run or workflow.",
    )

    causation_id: UUID | None = Field(
        default=None,
        description="The id of the event that directly caused this one, for tracing event chains.",
    )

    payload: PayloadT = Field(description="Event-specific data.")

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point for protocol/transport-level concerns "
        "(e.g. schema version, content type, delivery hints).",
    )

    @field_validator("event_type")
    @classmethod
    def _validate_event_type(cls, value: str) -> str:
        if not EVENT_TYPE_PATTERN.match(value):
            raise InvalidEventTypeError(
                f"event_type {value!r} must be lowercase, dot-namespaced, "
                "with at least two segments (e.g. 'error_rate.spiked')"
            )
        return value
