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

## Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs on every push to `main` and every pull request:

- **lint**: `ruff check` and `ruff format --check`
- **typecheck**: `ty check`
- **test**: unit tests, matrixed across Python 3.13 and 3.14
- **integration**: unit and integration tests together with the 80% coverage floor, matrixed across Python 3.13 and 3.14, on Docker-equipped runners
- **build**: `uv build`, with the resulting sdist and wheel uploaded as a workflow artifact

This mirrors the local pre-commit/pre-push hooks. The library supports Python 3.13 and later only (see `requires-python` in `pyproject.toml`), since `Event`'s generic payload default relies on `TypeVar(default=...)`, which is only available in the standard `typing` module from Python 3.13 onward.
