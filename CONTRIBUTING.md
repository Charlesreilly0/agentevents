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

## Branching and merging

This project uses trunk-based development: `main` is always the latest working state, and there are no long-lived `develop` or `release` branches.

- Branch off `main` for any change: `feat/<short-name>`, `fix/<short-name>`, `chore/<short-name>`, etc.
- Keep branches short-lived — open a PR as soon as the change is coherent, rather than accumulating unrelated work on one branch.
- Open a PR against `main` using the PR template. CI must pass (see above).
- Merge with **squash merge**. Each PR becomes exactly one commit on `main`; the squash commit message should be the PR title, written as a clear summary of the change (this becomes the permanent history and release notes source, so write it accordingly, not as "fix stuff").
- Delete the branch after merge.

Branch protection on `main` (PR required, CI checks required, no direct pushes) is documented here as the intended rule but is not yet enabled on GitHub, pending confirmation that push-triggered CI runs are reliable (see the note on the [GitHub Actions incident](https://www.githubstatus.com/) if `push` events aren't triggering runs).

## Versioning and releases

This project follows [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

- **MAJOR**: breaking changes to the public API (`Event`, `EventBus`, `Subscription`, exception types, or their behavior).
- **MINOR**: new functionality that's backward compatible (a new `EventBus` backend, a new field with a default, a new optional parameter).
- **PATCH**: backward-compatible bug fixes.

Before 1.0.0, the API may still shift between minor versions as the design settles — treat `0.x` releases as less strictly bound by these rules than `1.x` onward.

To cut a release:

1. On `main`, bump `version` in `pyproject.toml`.
2. Commit and push directly (or via PR) as `chore: release vX.Y.Z`.
3. Tag the commit and push the tag:

   ```
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

4. Pushing the tag triggers `.github/workflows/release.yml`, which verifies the tag matches `pyproject.toml`'s version, builds the sdist and wheel, and creates a GitHub Release with the build artifacts attached and auto-generated release notes.

Publishing to PyPI is not yet wired up — the release workflow currently stops at a GitHub Release. When ready to publish, add a `pypi-publish` step using [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC-based, no API token stored in the repo).
