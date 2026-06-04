# Changelog

All notable changes to Relinker will be documented in this file.

Relinker follows practical semantic versioning while the project is still pre-1.0. Breaking changes may happen before 1.0, but they should be documented clearly.

## 0.5.0

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
