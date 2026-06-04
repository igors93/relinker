# RetryFlow implementation patch

This ZIP contains replacement and new files using the same project structure.
Copy the files into the repository root and allow your file manager to replace
existing files.

## What changed

- Added `RetryPolicy.doctor()` with a `PolicyHealthReport`.
- Added `RetryPolicy.preview()` for a concise timing preview.
- Improved `RetryPolicy.explain()` to be more human-readable.
- Added event shortcut methods:
  - `on_before_attempt()`
  - `on_success()`
  - `on_failure()`
  - `on_retry()`
  - `on_giveup()`
- Added `RetryPolicy.with_structured_logging()` with safe JSON log fields.
- Hardened HTTP helpers with validation and safer `Retry-After` parsing.
- Added `http_retry_policy()` as a friendly HTTP recipe.
- Exported new public helpers from `retryflow.__init__`.
- Added tests for the new HTTP helpers and guidance features.

## Suggested checks

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pytest
```
