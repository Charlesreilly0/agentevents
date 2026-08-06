# Contributing

## Setup

This project uses [uv](https://github.com/astral-sh/uv).

```
uv sync
```

Install the pre-commit hooks so lint, formatting, type checking, and unit tests run automatically before each commit:

```
uv run pre-commit install
```

## Pre-commit checks

Every commit runs, in order: `ruff check --fix`, `ruff format`, `ty check`, and `uv run pytest` (unit tests only; integration tests are not run automatically since they need Docker). Run the full set manually at any time:

```
uv run pre-commit run --all-files
```

Type checking uses [ty](https://github.com/astral-sh/ty), Astral's type checker. It is still in early preview, so expect rough edges; if it becomes a blocker, `basedpyright` is a mature drop-in alternative already available in this environment.

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
