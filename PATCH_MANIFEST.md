# Relinker Retry Budget patch — 0.8.0

Extract this archive over the root of the `igors93/relinker` repository on top
of version 0.7.0 / branch `main`. Existing files in the archive are complete
replacements; new files retain their final repository paths.

## Public API

```python
from relinker import RetryBudget, RetryPolicy

budget = RetryBudget(max_retries=20, per=60)
policy = RetryPolicy().with_retry_budget(budget, key="payments-api")
```

## Added files

- `src/relinker/budget.py`
- `src/relinker/internal/retry_wait.py`
- `docs/retry-budgets.md`
- retry-budget unit and integration tests

## Main modified files

- `src/relinker/policy.py`
- sync and async executors
- sync and async context managers
- runtime state and state builder
- public exports, diagnostics text, structured logging, docs and version metadata

## Validation performed

- Ruff format check
- Ruff lint
- strict mypy
- full pytest suite with coverage
- package build
- strict Twine metadata validation
