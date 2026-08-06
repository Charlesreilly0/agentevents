class AgentEventsError(Exception):
    """Base class for all exceptions raised directly by this library."""


class InvalidEventTypeError(AgentEventsError, ValueError):
    """Raised when an event_type or subscription pattern is not valid.

    Subclasses ValueError so it still satisfies code that catches
    ValueError from Event construction (via pydantic), while letting
    callers that only care about this library catch InvalidEventTypeError
    specifically instead of a generic pydantic.ValidationError.
    """


class EventBusConnectionError(AgentEventsError):
    """Raised when an EventBus backend cannot be reached.

    Wraps the underlying backend-specific exception (e.g. a redis
    ConnectionError) so code written against the EventBus protocol can
    handle "the bus is unreachable" without importing a specific
    backend's exception types.
    """
