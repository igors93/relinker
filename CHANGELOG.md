# Changelog

All notable changes to RetryFlow are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## Unreleased

### Added

- `TryAgain` exception for explicit retry control from inside wrapped functions.
- `RetryWrappedFunction` Protocol for type-safe access to decorator attributes.
- `RetryPolicy.with_logging()` for standard library logging integration.
- `retryflow.http` module with `retry_if_status`, `should_retry_http_status`, `retry_after_delay`, and `parse_retry_after` helpers.
- New `RetryResult` properties: `last_error`, `last_value`, `failed_attempts`, `successful_attempts`, `error_types`.
- `RetryResult.summary()` method returning a compact dict suitable for logging.
- `RetrySimulation` new properties: `attempt_count`, `max_delay`, `stops_early`.
- `RetrySimulationAttempt.cumulative_sleep` field.
- `RetrySimulation.to_json()` method.
- New warning codes: `many_attempts`, `high_total_sleep`, `result_retry_without_observation`, `background_broad_exception`.
- New example files: `fake_services.py`, `retry_http_like.py`, `retry_database_like.py`, `retry_polling.py`, `retry_try_again.py`, `retry_with_logging.py`, `retry_production_checklist.py`.
- New docs: `try-again.md`, `http.md`, `production-checklist.md`, `common-patterns.md`, `release.md`.

### Changed

- `RetrySimulation.to_dict()` now includes `attempt_count`, `max_delay`, `stops_early`, and `cumulative_sleep` per attempt.
- `RetrySimulation.describe()` output now shows cumulative sleep, max delay, and attempt count.

---

## 0.4.0 — 2025-11-01

### Added

- Core retry execution engine (sync and async).
- Immutable `RetryPolicy` builder with fluent API.
- Delay strategies: fixed, linear, exponential, random exponential, random, chain, additive, custom.
- Retry conditions: exception-based, result-based, custom, composite (any/all).
- Stop strategies: attempt count, elapsed time, forever, composite.
- `RetryResult` with full attempt history and serialization.
- Events system with five event types.
- In-memory statistics via `RetryStats`.
- Diagnostics: `warnings()` and `simulate()` / `timeline()`.
- Context manager API (`for attempt in policy:`).
- Presets: `fast`, `network`, `database`, `patient`, `background_job`.
- Testing helpers: `no_sleep` context manager, `FailingTask`, `fail_times`.
- Full type annotations, mypy strict mode, ruff linting.
- Comprehensive test suite.

---

## 0.1.0

### Added

- Initial project scaffold.
- Retry decorator.
- RetryPolicy builder.
- Sync and async execution.
- Delay strategies.
- Retry conditions.
- Stop strategies.
- Result and attempt records.
- Events.
- Testing helpers.
