## Summary

Describe the problem and the smallest change that solves it.

## Scope

- [ ] The change is focused and does not include unrelated refactoring.
- [ ] No public API was changed unintentionally.
- [ ] Sync, async, decorator, and context-manager parity was considered.
- [ ] Documentation was updated when observable behavior changed.
- [ ] `CHANGELOG.md` was updated for user-visible or incompatible changes.

## Stability

- [ ] Existing contract and regression tests still pass.
- [ ] New behavior or bug fixes include focused tests.
- [ ] Retry, stop, delay, exhaustion, event, history, and retry-budget semantics remain predictable.
- [ ] No dependency was added without a clear maintenance justification.

## Validation

- [ ] `python -m ruff format --check .`
- [ ] `python -m ruff check .`
- [ ] `python -m mypy src`
- [ ] `python -m pytest --cov=relinker --cov-report=term-missing --cov-fail-under=85`
- [ ] `python -m build`
- [ ] `python -m twine check --strict dist/*`

## Public API

- [ ] Any intentional change to `relinker.__all__` updates the public API snapshot.
- [ ] Any intentional module-level API change updates compatibility documentation.
- [ ] Deprecation or migration guidance is included when needed.
