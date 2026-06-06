# Changelog

All notable changes to Relinker will be documented in this file.

Relinker follows practical semantic versioning while the project is still pre-1.0. Breaking changes may happen before 1.0, but they should be documented clearly.

## 0.7.0

### Added

- Added `RetryPolicy.keep_history(n)` to bound the number of `AttemptRecord` entries kept in memory (default: 1000). `RetryResult.attempt_count` now always reflects the true total even when history is bounded.
- Added `RetryResult.has_last_value` property to distinguish a successful `None` return from a run with no successful attempts.
- Added `MAX_RETRY_AFTER_SECONDS` constant (86 400 s) as a configurable safety cap for `parse_retry_after()`.
- Added `src/relinker/internal/executor_helpers.py` with shared `build_state`, `function_name`, and `normalize_retry_cause` helpers used by both executors and context managers to eliminate code duplication.

### Fixed

- `max_time()` now acts as a real time budget: the executor no longer sleeps past the deadline. If the computed delay would exceed the remaining budget the run is exhausted immediately instead of oversleeping.
- `RetryResult.last_value` and `RetryState.has_value` now correctly represent functions that return `None` (was returning `False`/`None` instead of the actual result).
- `parse_retry_after()` no longer returns arbitrarily large delays; values above `MAX_RETRY_AFTER_SECONDS` are capped and negative values fall back to the `default` argument.
- `ensure_non_negative()` and `ensure_positive()` now reject `NaN`, `inf`, and boolean arguments via `ensure_finite_float()`.
- Empty `AnyCondition`, `AllCondition`, `AnyStopStrategy`, and `AllStopStrategy` now raise `InvalidRetryConfigError` at construction time instead of producing silent undefined behaviour.
- Context manager exhaustion paths (`RetryAttemptContext`, `AsyncRetryAttemptContext`) now apply all `finish_exhausted()` behaviors (return_result, exhausted_callback, exhausted_exception_factory) consistently with the function executors. The combined `not should_retry or should_stop` branch was split into two explicit conditions.

### Changed

- `RetryResult.total_attempts` field added; `attempt_count` property now returns `total_attempts` when set, falling back to `len(attempts)` for backward compatibility.
- `SECURITY.md` expanded with sections on input validation, Retry-After safety cap, and memory/history limits.
- PyPI publish workflow now runs full lint, type checks, and tests before building; verifies version consistency, `py.typed` presence, and package metadata via `twine check --strict`.
- CI matrix extended to macOS and Python 3.13; added `pytest-cov` and a `validate-package` job with wheel smoke test.

## 0.6.1

### Changed

- Updated README with corrected installation instructions and usage examples.
- Updated documentation pages (`getting-started.md`, `installation.md`, `release.md`, `roadmap.md`).
- Added `Programming Language :: Python :: 3.12` and `Typing :: Typed` classifiers to `pyproject.toml`.

## 0.6.0

### Added

- Added `RetryPolicy.doctor()` for human-friendly policy health reports.
- Added `PolicyHealthReport` with risk levels and JSON-friendly output.
- Added `RetryPolicy.preview()` for concise retry timing previews.
- Added more human-friendly `RetryPolicy.explain()` output.
- Added shortcut event methods:
  - `on_before_attempt()`
  - `on_success()`
  - `on_failure()`
  - `on_retry()`
  - `on_giveup()`
- Added `with_structured_logging()` for compact JSON logs.
- Added dependency-free HTTP helpers:
  - `should_retry_http_status()`
  - `retry_if_status()`
  - `retry_after_delay()`
  - `parse_retry_after()`
  - `http_retry_policy()`
- Added safer handling for large or invalid `Retry-After` headers.
- Added documentation-focused examples for production-style workflows.

### Improved

- Improved policy diagnostics for risky retry loops.
- Improved simulation and preview readability.
- Improved structured logging safety by excluding error messages by default.
- Improved the public API exports for HTTP and diagnostics helpers.
- Improved tests around diagnostics, HTTP helpers, simulation, logging, and policy guidance.

### Notes

This release strengthens the core project direction:

> Simple by default, powerful by composition, safe by guidance.

## 0.4.0

### Added

- Added the initial public retry policy builder.
- Added retry decorator support.
- Added sync and async execution.
- Added retry by exception and result.
- Added core delay strategies.
- Added presets.
- Added result objects and statistics.
- Added initial diagnostics and simulation support.
