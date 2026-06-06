# Changelog

All notable changes to Relinker will be documented in this file.

Relinker follows semantic versioning. Public APIs introduced in `1.0.0` follow
the compatibility and deprecation policy documented in
`docs/reference/compatibility.md`.

## Unreleased

## 1.0.1 - 2026-06-06

### Fixed

- Budget reservation is now released when a `before_sleep` event handler raises
  an exception, across all execution paths (sync executor, async executor, sync
  context manager, async context manager).
- `max_time()` now evaluates elapsed time after `after_failure` event handlers
  run, so time consumed by handlers between the attempt end and the sleep
  decision is correctly counted against the configured budget.

## 1.0.0 - 2026-06-06

### Added

- Added behavioral contract tests covering sync, async, decorators, context managers, events, history, exhaustion, and retry budgets.
- Added documentation contracts for links, examples, versions, and documented imports.
- Added exact public API snapshots for `relinker.__all__` and `relinker.context.__all__`.
- Added an 85% coverage floor, documentation CI job, package export smoke checks, and a pull request checklist.

### Changed

- Centralized mutually exclusive exhaustion configuration in `RetryPolicy`.
- Centralized attempt history, aggregate counters, `RetryState`, and `RetryResult` construction in the internal `RetryRuntime`.
- Split context-manager support into focused sync, async, and shared modules while preserving existing imports.
- Reorganized documentation into guides, concepts, reference, and maintainer sections.

### Fixed

- Restored last-configuration-wins precedence for fallback, custom exhaustion exceptions, `return_result()`, and `raise_last()`.
- Removed the obsolete `return_result_precedence` diagnostic after contradictory exhaustion states became invalid.
- Kept explicit `None` results distinct from context blocks that did not call `set_result()`.

### Documentation

- Documented retry lifecycle, exhaustion behavior, compatibility tiers, architecture, public API, development checks, and release validation.

### Stable API

- `relinker.__all__` is the stable root public API. All names listed there are covered by the compatibility and deprecation policy starting from this release.
- `relinker.context.__all__` is a documented module API with the same stability guarantee.
- Behaviors protected by contracts include retry and stop decisions, exhaustion precedence, event names and order, `RetryResult` aggregate meanings, parity between sync, async, decorated, and context-manager execution, and the rule that an original call does not consume retry-budget capacity.
- Internal modules (`relinker.internal`, `relinker.context._shared`, underscore-prefixed objects) carry no compatibility guarantee.
- The deprecation policy documented in `docs/reference/compatibility.md` applies from this release.

## 0.8.0

### Added

- Added `RetryBudget(max_retries=..., per=...)` for process-local shared retry-rate protection.
- Added `RetryPolicy.with_retry_budget()` and `without_retry_budget()` with explicit keys.
- Added policy and budget delay details to `RetryState` and structured logs.
- Added deterministic unit, sync, async, cancellation, and context-manager tests.

### Behavior

- Only additional attempts consume capacity; the original call is never counted.
- Normal delays and shared budget waiting are combined into one actual sleep.
- `max_time()` includes budget waiting and rejected waits release their reservation.
- Interrupted or canceled sleeps release unused reservations and preserve the original interruption.
- Simulation does not invent shared runtime waits; `preview()` reports the limitation.

### Scope

- Retry budgets are in-memory and process-local, with no new runtime dependency.

## 0.7.0

### Added

- Added `RetryPolicy.keep_history(n)` to bound the number of `AttemptRecord` entries kept in memory (default: 1000). `RetryResult.attempt_count` now always reflects the true total even when history is bounded.
- Added `RetryResult.has_last_value` property to distinguish a successful `None` return from a run with no successful attempts.
- Added `MAX_RETRY_AFTER_SECONDS` constant (86 400 s) as a configurable safety cap for `parse_retry_after()`.
- Added `src/relinker/internal/executor_helpers.py` with shared `build_state`, `function_name`, and `normalize_retry_cause` helpers used by both executors and context managers to eliminate code duplication.

### Fixed

- `max_time()` now acts as a real time budget: the executor no longer sleeps past the deadline. If the computed delay would exceed the remaining budget the run is exhausted immediately instead of oversleeping.
- `RetryResult.last_value` and `RetryState.has_value` now correctly represent functions that return `None`.
- `parse_retry_after()` caps excessive values and rejects unsafe numeric configuration.
- Empty composite conditions and stop strategies now raise `InvalidRetryConfigError`.
- Context manager exhaustion paths now apply the same behavior as function executors.

### Changed

- Added complete-attempt counters independent of retained history.
- Expanded release, security, CI, package validation, and Python-version checks.

## 0.6.1

### Changed

- Updated README with corrected installation instructions and usage examples.
- Updated documentation pages and package classifiers.

## 0.6.0

### Added

- Added diagnostics, preview, event shortcuts, structured logging, HTTP helpers, and production guidance.

## 0.4.0

### Added

- Added the initial retry policy builder, decorator, sync/async execution, delay strategies, presets, results, statistics, diagnostics, and simulation support.
