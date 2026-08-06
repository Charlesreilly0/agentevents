# Examples

Runnable examples showing agentevents used together with other tools. Dependencies for examples live in their own `examples` dependency group, separate from the library's runtime and dev dependencies, so installing agentevents never pulls them in.

Install the group and run an example:

```
uv sync --group examples
uv run --group examples python examples/<example>.py
```

## pydantic_ai_incident_response.py

Two [Pydantic AI](https://ai.pydantic.dev/) agents coordinating through an `InMemoryEventBus` instead of calling each other directly: a monitoring agent publishes an `error_rate.spiked` event via a tool call, and a separate rollback agent subscribes to that event type and reacts, with no direct reference between the two.

Runs with `pydantic_ai.models.test.TestModel`, so it needs no API key. `TestModel` doesn't perform real inference — it calls the available tool with type-appropriate placeholder arguments, so the published event's values will be `0.0`, not values parsed from the prompt. Swap in a real model (e.g. `Agent("openai:gpt-4o", ...)`, with the corresponding API key set) to see the agent actually decide the values.
