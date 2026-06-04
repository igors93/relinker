# Roadmap

RetryFlow is currently pre-1.0. The API is stabilizing but not yet frozen.

## Current state (0.4.x)

The core library is complete:

- Immutable `RetryPolicy` builder with full fluent API.
- Sync and async execution engines.
- All delay strategies (fixed, linear, exponential, random, chain, additive, custom).
- All retry conditions (exception, result, custom, composite).
- All stop strategies (attempts, elapsed time, forever, composite).
- `TryAgain` explicit retry signal.
- `RetryResult` with full inspection API.
- Per-function statistics via `RetryStats`.
- Policy diagnostics: `warnings()`, `simulate()`, `timeline()`, `explain()`.
- Standard library logging integration via `with_logging()`.
- Dependency-free HTTP helpers in `retryflow.http`.
- Context manager retry blocks (`for attempt in policy:`).
- Presets: `fast`, `network`, `database`, `patient`, `background_job`.
- Testing helpers: `no_sleep`, `fail_times`.
- `RetryWrappedFunction` Protocol for type-safe decorated functions.
- Zero runtime dependencies.
- Python 3.10+ support.
- Full mypy strict compliance.

## Next steps (0.5.x)

- PyPI release (package is not yet published).
- Stable `1.0` API commitment.
- Optional OpenTelemetry integration.
- Optional CLI diagnostics tool.

## 1.0

- Stable public API with SemVer policy.
- PyPI release.
- Complete documentation site.
