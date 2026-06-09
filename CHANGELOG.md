# Changelog

All notable changes to Relinker will be documented in this file.

Relinker follows semantic versioning. Public APIs introduced in `1.0.0` follow
the compatibility and deprecation policy documented in
`docs/reference/compatibility.md`.

## Unreleased

### Fixed

- `RetryPolicy.run()` now rejects coroutine functions and async callable objects
  before execution instead of returning an unexecuted coroutine.

## 1.2.0 - 2026-06-08

### Added

- Added opt-in HTTP transport exception retries through
  `http_retry_policy(transport_exceptions=...)` and the
  `DEFAULT_RETRYABLE_TRANSPORT_EXCEPTIONS` helper constant. The default remains
  empty for `1.x` compatibility.
- Added the `implicit_default_policy` advisory warning for policies that still
  use broad `Exception`, three attempts, and no delay through implicit defaults.
- Added `failure_mode="isolate"` for event handlers, with built-in logging
  helpers using isolated observational handlers.
- Added permanent `RetryBudget` property and concurrency tests plus maintainer
  documentation for rolling-window, earliest-slot, atomicity, release, and
  snapshot invariants.

### Changed

- CI now tests Python 3.14 and Windows in addition to the existing Linux and
  macOS compatibility matrix.
- Refactored small deterministic executor-flow helpers shared by sync, async,
  and block paths while keeping their loops, sleeps, and await points explicit.

### Documentation

- Added troubleshooting guide organized by symptom: function did not retry,
  retried too many times, slow execution, synchronized retries, unexpected final
  error, async handler rejected, generator rejected.
- Added choosing-a-policy guide with a decision tree and starting configurations
  for external APIs, rate-limited APIs, databases, background jobs, and polling.
- Added common-mistakes guide with wrong/better patterns for broad exception
  retry, infinite retry without delay, missing jitter, many attempts without a
  budget, silent fallback, non-idempotent operations, and tests with real sleep.
- Added feature-map reference page for quick lookup from need to API.
- Expanded when-not-to-retry guide with idempotency explanation, idempotency
  table by operation, generator rejection, async handler rejection, permanent
  failure examples, and max_time clarification.
- Expanded getting-started guide with a conceptual introduction to temporary
  versus permanent failures before the first code example.
- Expanded async guide with CancelledError behavior, async handler rejection
  explanation, and async testing example.
- Expanded production-checklist guide with explanations for each item.
- Updated documentation index with new pages and extended learning path.
- Updated compatibility documentation to state the official Python 3.10 through
  Python 3.14 support range consistently.

### Fixed

- `TryAgain` now preserves the real retry cause in result history and final
  errors, including explicit causes, implicit contexts, and plain `TryAgain`
  exceptions.
- Generator and async-generator functions are now rejected because exceptions
  raised during iteration occur outside the retry call and cannot be retried
  safely.
- Async event handlers are now rejected explicitly instead of creating an
  unawaited coroutine, including partial-wrapped callable handler objects.
- Corrected callable-kind detection for `functools.partial` wrapping callable
  objects, so async `__call__` targets are decorated as async wrappers while
  sync, generator, async-generator, nested partial, and callable-class cases keep
  their safe contracts.
- Corrected `with_policy()` typing so replacement policies no longer imply
  that the wrapped function changes its underlying return type.
- `add_delay()` and `jitter()` now preserve `AdditiveDelay` grouping so
  floating-point addition order is not changed silently. Deep additive-delay
  trees are evaluated, inspected, and serialized iteratively to prevent
  recursion errors without flattening the arithmetic structure.
- `RetryBudget` no longer places a reservation inside a full window when
  `per` is a decimal value whose floating-point arithmetic causes
  `(first + per) - per < first`. `_first_legal_slot` now re-scans after each
  boundary advance and, when a candidate lands exactly on a boundary that
  rounds back into the window, steps forward by one ULP and re-scans rather
  than walking one representable float at a time while holding the budget lock.

## 1.1.0 - 2026-06-07

### Added

- Added policy names with `RetryPolicy.named(...)`, propagated to retry state, events,
  results, logs, structured logs, explanations, and policy dictionaries.
- Added `RetryLoadEstimate` and `RetryPolicy.estimate_load(...)` for explicit
  worst-case load estimates under concurrency.
- Added `RetryPolicy.to_dict()` for a structured, log-safe view of policy
  configuration.
- Added `relinker.result_conditions` helpers for common result-based retry
  predicates.
- Expanded `doctor()` guidance with warnings for missing jitter, missing retry
  budgets, silent fallbacks, infinite retry with a budget, and `for_testing()`
  combined with `max_time()`.

### Fixed

- Corrected load estimates for `ALL` stop strategies containing an unbounded condition.
- Corrected load estimates for `OR` stop strategies so mixed bounded and
  unbounded branches are reported as partial rather than fully unbounded.
- Corrected `RetryPolicy.to_dict()` to describe result exhaustion separately.
- Corrected testing-mode metadata when custom sleep functions replace `for_testing()`.
- Restored default async sleep behavior when `with_sleep()` replaces only the
  sync sleeper after `for_testing()`.
- Validated resolved delays centrally after custom and composed delay strategies.
- Ensured configured exhaustion exception instances are copied per exhaustion.
- Honored `minimum` for zero-base `random_exponential_delay()` strategies.
- Improved diagnostics for composed stop and exception conditions.
- Clarified `simulate()` documentation for unsupported custom and stateful delay
  callbacks.
- Corrected `@retry(return_result=True)` typing to return `RetryResult`.
- Clarified `Retry-After` documentation so invalid values fall back while large
  valid values are capped.
- Clarified `retry_if()` documentation for callbacks receiving a real `None`
  result.
- `RetryBudget` now reserves the first legal slot instead of treating distant
  future reservations as blockers.
- `RetryBudgetSnapshot` now distinguishes active reservations from future queued
  reservations and reports immediate availability and next availability.

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
