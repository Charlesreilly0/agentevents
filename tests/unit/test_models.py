import pytest
from pydantic import BaseModel, ValidationError

from agentevents.exceptions import InvalidEventTypeError
from agentevents.models import Event


class ErrorRateSpiked(BaseModel):
    rate: float
    threshold: float


@pytest.mark.parametrize(
    "event_type",
    [
        "error_rate.spiked",
        "deploy.prod.rollback.triggered",
        "a.b",
    ],
)
def test_valid_event_type(event_type: str) -> None:
    event = Event(event_type=event_type, source="agent", payload={})
    assert event.event_type == event_type


@pytest.mark.parametrize(
    "event_type",
    [
        "deploy",
        "Deploy.Started",
        "deploy.",
        ".deploy",
        "deploy..started",
        "deploy started",
        "",
    ],
)
def test_invalid_event_type_rejected(event_type: str) -> None:
    with pytest.raises(ValidationError):
        Event(event_type=event_type, source="agent", payload={})


def test_invalid_event_type_cause_is_invalid_event_type_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Event(event_type="bad", source="agent", payload={})
    assert isinstance(exc_info.value.errors()[0]["ctx"]["error"], InvalidEventTypeError)


def test_payload_is_required() -> None:
    with pytest.raises(ValidationError):
        Event(event_type="deploy.started", source="agent")


def test_plain_event_accepts_dict_payload() -> None:
    event = Event(event_type="deploy.started", source="agent", payload={"env": "prod"})
    assert event.payload == {"env": "prod"}


def test_generic_event_validates_typed_payload() -> None:
    event = Event[ErrorRateSpiked](
        event_type="error_rate.spiked",
        source="monitor",
        payload=ErrorRateSpiked(rate=0.5, threshold=0.1),
    )
    assert isinstance(event.payload, ErrorRateSpiked)
    assert event.payload.rate == 0.5


def test_generic_event_rejects_invalid_typed_payload() -> None:
    with pytest.raises(ValidationError):
        Event[ErrorRateSpiked](
            event_type="error_rate.spiked",
            source="monitor",
            payload={"rate": "not-a-float", "threshold": 0.1},
        )


def test_correlation_and_causation_default_to_none() -> None:
    event = Event(event_type="deploy.started", source="agent", payload={})
    assert event.correlation_id is None
    assert event.causation_id is None


def test_id_and_timestamp_are_auto_generated() -> None:
    a = Event(event_type="deploy.started", source="agent", payload={})
    b = Event(event_type="deploy.started", source="agent", payload={})
    assert a.id != b.id
    assert a.timestamp is not None
