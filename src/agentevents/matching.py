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
