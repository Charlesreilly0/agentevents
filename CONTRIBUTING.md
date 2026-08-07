# Contributing

## Documentation structure

API/user-facing reference documentation lives in `docs/` (`docs/api.md`, `docs/backend-guide.md`), not in `README.md`, and is reviewed via normal PRs like any other change. `.github/workflows/wiki-sync.yml` mirrors `docs/` to the [GitHub wiki](https://github.com/Charlesreilly0/agentevents/wiki) on every push to `main` that touches `docs/**`, so `docs/` is the source of truth and the wiki is a generated mirror — never edit the wiki directly, edits there are overwritten on the next sync. `README.md` stays limited to what the library is, installation, and a quickstart, with links into `docs/`.

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

Branch protection on `main` is enabled: a PR is required, all seven CI check runs must pass and be up to date with `main` (lint, typecheck, unit tests on 3.13/3.14, integration tests on 3.13/3.14, build), and force-pushes/branch deletion are blocked. This was deliberately deferred earlier while GitHub Actions was mid-incident (webhook delivery throttled, so required checks could have gotten stuck pending forever) and enabled once push-triggered runs were confirmed reliable again via the Actions API.

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

5. Pushing the tag triggers `.github/workflows/release.yml`: the `release` job verifies the tag matches `pyproject.toml`'s version, builds the sdist and wheel, and creates a GitHub Release with the build artifacts attached and auto-generated release notes. The `publish-pypi` job then downloads those same artifacts and publishes them to PyPI via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) — OIDC-based, no API token stored in the repo.

### One-time PyPI setup

`publish-pypi` will fail with an authentication error until this is done once, on PyPI's side (not something that can be configured from this repository):

1. On PyPI, either create the `agentevents` project first, or use [pending trusted publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/) to register a trusted publisher before the project exists yet.
2. Add a trusted publisher with: repository owner `Charlesreilly0`, repository name `agentevents`, workflow filename `release.yml`, environment name `pypi`.

The `pypi` GitHub Actions environment referenced in `release.yml` is auto-created on first use if it doesn't already exist. Add required reviewers to it (Settings → Environments → `pypi` → Deployment protection rules) if you want a manual approval step before every PyPI publish — publishing a version to PyPI cannot be undone (the same version number can never be re-uploaded), so this is worth doing before the first real release.

## Keeping the changelog current

Every PR that changes user-facing behavior (public API, CLI, packaging) should add an entry under `## [Unreleased]` in `CHANGELOG.md`, in the appropriate [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) category (Added, Changed, Fixed, Removed, etc.). Internal-only changes (test refactors, CI tweaks) don't need an entry unless they affect how someone uses or contributes to the library.

## Implementing a new EventBus backend

See [docs/backend-guide.md](docs/backend-guide.md).
