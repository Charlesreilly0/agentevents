import pytest

from agentevents.exceptions import InvalidEventTypeError
from agentevents.matching import matches, validate_pattern


@pytest.mark.parametrize(
    ("pattern", "event_type", "expected"),
    [
        ("error_rate.spiked", "error_rate.spiked", True),
        ("error_rate.spiked", "error_rate.recovered", False),
        ("error_rate.*", "error_rate.spiked", True),
        ("error_rate.*", "error_rate.recovered", True),
        ("error_rate.*", "deploy.started", False),
        ("*.spiked", "error_rate.spiked", True),
        ("*.spiked", "error_rate.recovered", False),
        ("*", "error_rate", True),
        ("*", "error_rate.spiked", False),
        ("deploy.>", "deploy.started", True),
        ("deploy.>", "deploy.prod.rollback", True),
        ("deploy.>", "rollback.started", False),
        ("deploy.>", "deploy", False),
        (">", "a", True),
        (">", "a.b.c", True),
        ("a.*.c", "a.b.c", True),
        ("a.*.c", "a.b.d", False),
        ("a.b", "a.b.c", False),
        ("a.b.c", "a.b", False),
    ],
)
def test_matches(pattern: str, event_type: str, expected: bool) -> None:
    assert matches(pattern, event_type) is expected


@pytest.mark.parametrize(
    "pattern",
    [
        "error_rate.*",
        "*.spiked",
        "deploy.>",
        ">",
        "a.b.c",
        "task_123.done",
        "*",
    ],
)
def test_validate_pattern_accepts_valid_patterns(pattern: str) -> None:
    validate_pattern(pattern)


@pytest.mark.parametrize(
    "pattern",
    [
        "",
        "deploy.>.rollback",
        "a..b",
        ".a",
        "a.",
        "Deploy.Started",
        "a.b c",
        "a.b-c",
    ],
)
def test_validate_pattern_rejects_invalid_patterns(pattern: str) -> None:
    with pytest.raises(InvalidEventTypeError):
        validate_pattern(pattern)
