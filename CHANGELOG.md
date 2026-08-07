# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

Nothing has been released yet. Everything below is part of the initial, unreleased `0.1.0` line.

### Added

- `Event`, a Pydantic model for agent-to-agent events: dot-namespaced `event_type` (validated, wildcard-matchable), `source`, `id`, `timestamp`, `correlation_id`/`causation_id` for tracing event chains, an open `metadata` dict, and a `payload` generic over an optional typed model.
- `EventBus` protocol with `publish`/`subscribe`/`subscriber_count`, and `Subscription`, an async context manager guaranteeing deterministic unsubscribe on block exit (`break`, return, or exception) rather than relying on generator garbage-collection timing.
- `InMemoryEventBus`: an `EventBus` backed by per-subscriber bounded `asyncio.Queue`s with drop-oldest backpressure, for local development and single-process use.
- `RedisEventBus`: an `EventBus` backed by Redis Pub/Sub, letting independent processes/agents share a bus over a single channel with the same wildcard matching and backpressure semantics as the in-memory implementation.
- `*`/`>` wildcard subscription pattern matching (`agentevents.matching.matches`, `validate_pattern`), matching NATS/MQTT-style topic conventions.
- Typed subscriptions via `subscribe(pattern, payload_type=SomeModel)`, validating/coercing each event's payload; malformed payloads are logged and skipped rather than raised.
- `AgentEventsError`, `InvalidEventTypeError`, and `EventBusConnectionError` as a library-specific exception hierarchy, so callers don't need backend-specific exception types (e.g. `redis.exceptions`) to handle a down `EventBus`.
- `examples/pydantic_ai_incident_response.py`, showing two [Pydantic AI](https://ai.pydantic.dev/) agents coordinating through an `InMemoryEventBus` instead of calling each other directly, in a dedicated `examples` dependency group.
- `examples/causation_chain.py`, showing `correlation_id`/`causation_id` in use: three agents reacting to each other in sequence through an `InMemoryEventBus`, all sharing one `correlation_id`, each event's `causation_id` pointing at the one before it, reconstructed into a printed chain at the end. Needs no extra dependencies.
- Unit and integration (Redis via [testcontainers](https://testcontainers.com/)) test suites, pre-commit hooks (ruff, [ty](https://github.com/astral-sh/ty), unit tests) and a pre-push gate (full test suite, 80% combined coverage floor, package build).
- GitHub Actions CI (lint, type check, unit tests across Python 3.13/3.14, integration tests with coverage, build) and a tag-triggered release workflow that builds the package, creates a GitHub Release, and publishes to PyPI via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC, no stored token).
- Branch protection on `main`: PR required, all CI check runs required and must be up to date, force-pushes and branch deletion blocked. Squash-only merging and automatic branch deletion on merge enforced at the repo level.
- Dependabot for `uv`-ecosystem dependencies and GitHub Actions versions, weekly, grouped by dev/non-dev and by all actions respectively, with commit messages matching this project's `type: summary` convention.

### Documentation

- `README.md` covering installation and a quickstart, linking into `docs/` for API reference and the backend implementation guide.
- `docs/api.md`: `Event`, both `EventBus` implementations, pattern matching, typed subscriptions, backpressure, and the exception hierarchy. `docs/backend-guide.md`: what's reusable vs. backend-specific when implementing a new `EventBus`. Synced to the [GitHub wiki](https://github.com/Charlesreilly0/agentevents/wiki) on push to `main` (`.github/workflows/wiki-sync.yml`); `docs/` is the source of truth, the wiki is a generated mirror.
- `CONTRIBUTING.md` covering setup, pre-commit/pre-push checks, running tests (including the Colima/Ryuk testcontainers workaround), examples, branching and merging (trunk-based, squash-only merges, enforced at the repo level), and the versioning/release process.
- A pull request template matching the checks the CI pipeline actually runs.

[Unreleased]: https://github.com/Charlesreilly0/agentevents/commits/main
