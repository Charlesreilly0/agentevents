## Summary

<!-- What does this change do, and why? -->

## Checklist

- [ ] `uv run pre-commit run --all-files` passes locally
- [ ] `uv run pytest -m integration` passes locally (if this touches `RedisEventBus` or the `EventBus` protocol)
- [ ] Tests added or updated for the change
- [ ] README / CONTRIBUTING updated if behavior or setup steps changed
- [ ] `CHANGELOG.md` updated under `[Unreleased]` if this changes user-facing behavior
