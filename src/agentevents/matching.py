from __future__ import annotations

from agentevents.exceptions import InvalidEventTypeError


def validate_pattern(pattern: str) -> None:
    """
    Raise InvalidEventTypeError if pattern is not a usable subscription
    pattern: non-empty, dot-separated segments, each either a literal
    lowercase/digit/underscore segment, "*", or ">" appearing only as the
    final segment.
    """
    if not pattern:
        raise InvalidEventTypeError("pattern must not be empty")

    segments = pattern.split(".")
    for i, seg in enumerate(segments):
        if seg == "":
            raise InvalidEventTypeError(
                f"pattern {pattern!r} has an empty segment"
            )
        if seg == ">":
            if i != len(segments) - 1:
                raise InvalidEventTypeError(
                    f"pattern {pattern!r} has '>' before the final segment; "
                    "'>' must be the last segment"
                )
            continue
        if seg == "*":
            continue
        if not seg.replace("_", "").isalnum() or not seg.islower():
            raise InvalidEventTypeError(
                f"pattern {pattern!r} has invalid segment {seg!r}; segments "
                "must be lowercase alphanumeric/underscore, '*', or a "
                "trailing '>'"
            )


def matches(pattern: str, event_type: str) -> bool:
    """
    Match a dot-namespaced event_type against a subscription pattern.

    Pattern segments:
      - a literal segment must match exactly
      - "*" matches exactly one segment
      - ">" matches one or more trailing segments, and must be the last
        segment in the pattern
    """
    pattern_segments = pattern.split(".")
    event_segments = event_type.split(".")

    for i, pseg in enumerate(pattern_segments):
        if pseg == ">":
            return i < len(event_segments)

        if i >= len(event_segments):
            return False

        if pseg != "*" and pseg != event_segments[i]:
            return False

    return len(pattern_segments) == len(event_segments)
