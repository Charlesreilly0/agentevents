# Examples

Runnable examples showing agentevents in use. Some depend on extra packages the library itself does not (e.g. `pydantic-ai`), kept in their own `examples` dependency group so installing agentevents never pulls them in.

```
uv run python examples/<example>.py
```

If an example needs the `examples` group (noted below), install it first:

```
uv sync --group examples
uv run --group examples python examples/<example>.py
```

## causation_chain.py

Needs only `agentevents` — no extra dependencies.

Three agents react to each other in sequence purely through an `InMemoryEventBus`, with no agent calling another directly: a monitoring agent detects a spike and publishes `error_rate.spiked`; a rollback agent reacts and publishes `rollback.triggered`; a notification agent reacts to that and publishes `notification.sent`. Every event in the chain shares one `correlation_id`, and each event's `causation_id` points at the id of the event that triggered it. The example ends by walking the chain back to its root via `causation_id` and printing it — the thing `correlation_id`/`causation_id` on `Event` are for, made concrete.

## pydantic_ai_incident_response.py

Needs the `examples` dependency group (`pydantic-ai`).

Two [Pydantic AI](https://ai.pydantic.dev/) agents coordinating through an `InMemoryEventBus` instead of calling each other directly: a monitoring agent publishes an `error_rate.spiked` event via a tool call, and a separate rollback agent subscribes to that event type and reacts, with no direct reference between the two.

Runs with `pydantic_ai.models.test.TestModel`, so it needs no API key. `TestModel` doesn't perform real inference — it calls the available tool with type-appropriate placeholder arguments, so the published event's values will be `0.0`, not values parsed from the prompt. Swap in a real model (e.g. `Agent("openai:gpt-4o", ...)`, with the corresponding API key set) to see the agent actually decide the values.
