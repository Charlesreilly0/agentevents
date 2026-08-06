# Contributing

## Setup

This project uses [uv](https://github.com/astral-sh/uv).

```
uv sync
```

Install the pre-commit and pre-push hooks:

```
uv run pre-commit install
uv run pre-commit install --hook-type pre-push
```

## Pre-commit checks

Every commit runs, in order: `ruff check --fix`, `ruff format`, `ty check`, and `uv run pytest` (unit tests only; integration tests are not run automatically since they need Docker). Run the full set manually at any time:

```
uv run pre-commit run --all-files
```

Type checking uses [ty](https://github.com/astral-sh/ty), Astral's type checker. It is still in early preview, so expect rough edges; if it becomes a blocker, `basedpyright` is a mature drop-in alternative already available in this environment.

## Pre-push checks

Every push runs the full test suite (unit and integration together, so Docker is required), enforces at least 80% combined statement coverage, and builds the package (sdist and wheel) to catch packaging issues before they would surface as a broken PyPI release. Run it manually at any time:

```
uv run pre-commit run --hook-stage pre-push --all-files
```

Coverage is measured across unit and integration tests together, not unit tests alone — the Redis backend is only exercised by integration tests, so a unit-only run sits well under 80%. This is intentional: the fast unit-only gate stays fast, and the full coverage bar is enforced where Docker is already required.

## Tests

Unit tests do not need Docker and run by default:

```
uv run pytest
```

Integration tests use [testcontainers](https://testcontainers.com/) to start a real Redis in Docker. They are excluded from the default run and must be requested explicitly:

```
uv run pytest -m integration
```

### Docker via Colima

If Docker is provided by Colima or another non-default runtime, testcontainers' cleanup container (Ryuk) can fail to start, because of how its socket is mounted. The error looks like:

```
docker.errors.APIError: 500 Server Error ... error while creating mount source path
'/Users/you/.colima/default/docker.sock': mkdir ...: operation not supported
```

If you hit this, disable Ryuk and let the test fixtures clean up containers themselves:

```
TESTCONTAINERS_RYUK_DISABLED=true uv run pytest -m integration
```

## Running the CLI

```
uv run agentevents
```

## Examples

Runnable examples live in `examples/` and depend on things the library itself does not (e.g. `pydantic-ai`), kept in their own `examples` dependency group so they're never installed by default:

```
uv sync --group examples
uv run --group examples python examples/<example>.py
```

`examples/` is excluded from `ty check .` (see `[tool.ty.src] exclude` in `pyproject.toml`), since the default dev environment doesn't have the `examples` group installed and `ty` would otherwise fail to resolve those imports. If you change an example, type-check it explicitly by file (checking the `examples/` directory itself is a no-op, since the exclude glob prunes the whole directory before ty walks it):

```
uv run --group examples ty check examples/<example>.py
```

## Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs on every push to `main` and every pull request:

- **lint**: `ruff check` and `ruff format --check`
- **typecheck**: `ty check`
- **test**: unit tests, matrixed across Python 3.13 and 3.14
- **integration**: unit and integration tests together with the 80% coverage floor, matrixed across Python 3.13 and 3.14, on Docker-equipped runners
- **build**: `uv build`, with the resulting sdist and wheel uploaded as a workflow artifact

This mirrors the local pre-commit/pre-push hooks. The library supports Python 3.13 and later only (see `requires-python` in `pyproject.toml`), since `Event`'s generic payload default relies on `TypeVar(default=...)`, which is only available in the standard `typing` module from Python 3.13 onward.

### Dependency updates

[Dependabot](https://docs.github.com/en/code-security/dependabot) (`.github/dependabot.yml`) opens weekly PRs for outdated dependencies (`uv` ecosystem, covering `pyproject.toml`/`uv.lock`) and GitHub Actions versions used in workflows. This replaces manually checking whether an action tag like `astral-sh/setup-uv@vX` actually exists before bumping it.

Dependabot PRs still need to pass the same CI and review as any other PR before merging. If a Dependabot PR bumps `pyproject.toml` without updating `uv.lock` to match, run `uv sync` locally and push the updated lockfile before merging.

## Branching and merging

This project uses trunk-based development: `main` is always the latest working state, and there are no long-lived `develop` or `release` branches.

- Branch off `main` for any change: `feat/<short-name>`, `fix/<short-name>`, `chore/<short-name>`, etc.
- Keep branches short-lived — open a PR as soon as the change is coherent, rather than accumulating unrelated work on one branch.
- Open a PR against `main` using the PR template. CI must pass (see above).
- Merge with **squash merge** — this is enforced at the repo level; merge commit and rebase merge are disabled, so squash is the only option GitHub offers. The squash commit message defaults to the PR title, which becomes the permanent history and release notes source, so write PR titles as clear summaries of the change, not as "fix stuff."
- Branches are deleted automatically on merge (also enforced at the repo level).

Branch protection on `main` (PR required, CI checks required, no direct pushes) is documented here as the intended rule but is not yet enabled on GitHub, pending confirmation that push-triggered CI runs are reliable (see the note on the [GitHub Actions incident](https://www.githubstatus.com/) if `push` events aren't triggering runs). The merge-strategy settings above (squash-only, auto-delete) are unrelated to that incident and are already enforced.

## Versioning and releases

This project follows [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

- **MAJOR**: breaking changes to the public API (`Event`, `EventBus`, `Subscription`, exception types, or their behavior).
- **MINOR**: new functionality that's backward compatible (a new `EventBus` backend, a new field with a default, a new optional parameter).
- **PATCH**: backward-compatible bug fixes.

Before 1.0.0, the API may still shift between minor versions as the design settles — treat `0.x` releases as less strictly bound by these rules than `1.x` onward.

To cut a release:

1. On `main`, bump `version` in `pyproject.toml`.
2. In `CHANGELOG.md`, rename the `## [Unreleased]` section to `## [X.Y.Z] - YYYY-MM-DD` and add a fresh empty `## [Unreleased]` section above it. Update the `[Unreleased]` and new version's link references at the bottom of the file.
3. Commit and push directly (or via PR) as `chore: release vX.Y.Z`.
4. Tag the commit and push the tag:

   ```
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

5. Pushing the tag triggers `.github/workflows/release.yml`, which verifies the tag matches `pyproject.toml`'s version, builds the sdist and wheel, and creates a GitHub Release with the build artifacts attached and auto-generated release notes.

Publishing to PyPI is not yet wired up — the release workflow currently stops at a GitHub Release. When ready to publish, add a `pypi-publish` step using [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC-based, no API token stored in the repo).

## Keeping the changelog current

Every PR that changes user-facing behavior (public API, CLI, packaging) should add an entry under `## [Unreleased]` in `CHANGELOG.md`, in the appropriate [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) category (Added, Changed, Fixed, Removed, etc.). Internal-only changes (test refactors, CI tweaks) don't need an entry unless they affect how someone uses or contributes to the library.

## Implementing a new EventBus backend

`agentevents` ships two backends: `InMemoryEventBus` (single process, `src/agentevents/bus/memory.py`) and `RedisEventBus` (Redis Pub/Sub, `src/agentevents/bus/redis.py`). A new backend — NATS, Kafka, Redis Streams, a cloud pub/sub service — needs to satisfy the `EventBus` and `Subscription` protocols in `src/agentevents/bus/protocol.py`. Read both existing implementations side by side before starting; they're deliberately similar, and the diff between them is exactly the part that's backend-specific.

### What's reusable as-is

The two existing backends share almost the entire `_Subscription` implementation verbatim:

- A bounded `asyncio.Queue[Event[Any]]` per subscription, with an `offer()` method that does drop-oldest backpressure (`put_nowait`, and on `QueueFull`, evict the oldest item, increment a `dropped` counter, log a warning, then enqueue the new one). This is transport-independent — copy it.
- `__anext__` pulling off that local queue and, if `payload_type` isn't `dict`, validating/coercing the payload via `pydantic.TypeAdapter`, logging and skipping (not raising) on a mismatch so one malformed event doesn't kill the subscriber loop.
- `__aenter__`/`__aiter__` returning `Self` (not a quoted class name — see `from __future__ import annotations` at the top of both files), and `__aexit__` calling `unsubscribe()`. This is what makes `async with bus.subscribe(...) as sub: ...` deterministic: `__aexit__` is guaranteed to run synchronously on block exit (return, `break`, or exception), unlike relying on an async generator's `finally`, which only runs on garbage collection — a bug we hit and fixed during this library's own development. Don't reintroduce it by returning a bare async generator from `subscribe()`.
- `unsubscribe()` being idempotent (`if not self._active: return`), and `subscriber_count()`'s implementation (count `self._subscriptions`, optionally filtered by exact pattern string — not a wildcard match).
- `validate_pattern(pattern)` at the top of `subscribe()`, before constructing anything. Every backend must call this; it's what makes a malformed pattern (`"deploy.>.rollback"`, an empty segment, uppercase) fail loudly at subscribe time instead of silently matching nothing forever.

### What's actually backend-specific

Only one thing genuinely differs between backends: **how an event gets from `publish()` into a subscription's `offer()`**. Compare the two:

- `InMemoryEventBus.publish()` just loops over `self._subscriptions` in-process and calls `matches(sub.pattern, event.event_type)` / `sub.offer(event)` directly — no network, no serialization.
- `RedisEventBus.publish()` serializes the `Event` to JSON and does `PUBLISH` on a shared channel; a single background listener task (`_listen()`, started lazily on first subscription via `_ensure_listener()`) reads every message off that channel, deserializes it, and does the same `matches()` / `offer()` fan-out to every local subscription. Every subscriber process receives every published event and filters client-side, because Redis Pub/Sub has no `*`/`>` wildcard concept of its own.

A new backend's job is to answer: **does the underlying transport support server-side subject/topic wildcards matching our `*`/`>` grammar, or does it need client-side filtering like Redis?**

- If yes (NATS subjects are the closest native match — `*` for one token, `>` for trailing tokens, nearly identical to our grammar), you may be able to subscribe per-pattern directly against the transport instead of one shared channel + local `matches()` calls. This is more efficient (the broker filters before sending you anything) but means `subscribe()` needs to do real I/O (open a transport-level subscription), which `InMemoryEventBus.subscribe()` doesn't — see the next point.
- If no (Kafka, Redis Streams, most cloud pub/sub), follow the `RedisEventBus` shape: one shared topic/stream, one listener loop, client-side `matches()` filtering into local queues.

### The subscribe() I/O problem

`EventBus.subscribe()` is a **synchronous** method in the protocol (it has to be, so it can be called before any `await`). But most real transports need async I/O to actually register a subscription (open a connection, call `SUBSCRIBE`). `RedisEventBus` solves this by making `subscribe()` synchronous and cheap (just append to a local list) and deferring the real connection work to `_ensure_listener()`, called from `Subscription.__aenter__` and `__anext__` — i.e., the first time the subscription is actually used inside an `async with` block, not when `subscribe()` is called. Follow this pattern rather than trying to make `subscribe()` itself async (it can't be, without breaking the protocol).

### Error handling

Wrap the underlying client library's connection/transport errors in `EventBusConnectionError` (`src/agentevents/exceptions.py`) at the points where your backend actually talks to the network — see `RedisEventBus._ensure_listener()` and `.publish()` for the pattern (`except <library>Error as exc: raise EventBusConnectionError(...) from exc`). This is the whole point of having a library-specific exception: code written against `EventBus` shouldn't need to import a specific backend's exception types to handle "the bus is unreachable."

### Testing a new backend

Mirror the existing test layout:

- `tests/unit/` — if any part of your backend can be tested without the real transport (e.g., a pure serialization/deserialization round-trip), it belongs here.
- `tests/integration/`, marked `@pytest.mark.integration`, using [testcontainers](https://testcontainers.com/) if a containerized version of your backend exists (see `tests/integration/conftest.py`'s `redis_url` fixture for the pattern). At minimum, mirror `tests/integration/test_bus_redis.py`'s coverage: publish/subscribe within one bus instance, wildcard filtering, two separate bus instances communicating (the test that actually proves cross-process behavior), typed payload coercion, backpressure/drop-oldest, deterministic cleanup on `break`, `subscriber_count`, invalid pattern rejection, and connection-error wrapping against an unreachable server.

Open an issue or discussion making the case for a specific transport before writing a full backend — backends aren't added speculatively here, so a concrete reason (a real workload that needs replay, or a team already standardized on a given broker) is worth more than "more options."
