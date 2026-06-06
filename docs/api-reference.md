# API Reference

This is a high-level public API reference. Internal modules may change.

## Core

| Name | Purpose |
|---|---|
| `retry` | Simple decorator entry point |
| `RetryPolicy` | Fluent policy builder |
| `RetryBudget` | Shared process-local retry capacity |
| `RetryResult` | Rich execution result |
| `RetryState` | Immutable runtime state snapshot |
| `RetryEvent` | Event object used by hooks |

## Presets

| Name | Purpose |
|---|---|
| `fast()` | Small and quick retry policy |
| `network()` | Network and external API calls |
| `database()` | Database-like transient failures |
| `patient()` | Slower retry policy for operations that can wait |
| `background_job()` | Background workers and scheduled jobs |

## Diagnostics

| Name | Purpose |
|---|---|
| `PolicyWarning` | Advisory warning about a policy |
| `PolicyHealthReport` | Doctor report for a policy |
| `RetrySimulation` | Simulated retry timeline |
| `RetrySimulationAttempt` | One simulated attempt |

## HTTP

| Name | Purpose |
|---|---|
| `DEFAULT_RETRYABLE_STATUSES` | Default retryable HTTP statuses |
| `should_retry_http_status()` | Check if a status should retry |
| `retry_if_status()` | Build a result predicate for HTTP responses |
| `retry_after_delay()` | Build a state-aware delay from `Retry-After` |
| `parse_retry_after()` | Parse a `Retry-After` header |
| `http_retry_policy()` | Ready-to-use HTTP retry policy |

## Exceptions

| Name | Purpose |
|---|---|
| `RelinkerError` | Base Relinker exception |
| `InvalidRetryConfigError` | Invalid configuration |
| `RetryExhaustedError` | Result retry exhausted explicitly |
| `TryAgain` | Explicit retry signal |

## RetryPolicy method groups

### Stop

- `attempts()`
- `max_time()`
- `forever()`
- `stop_when()`
- `or_stop_after_attempts()`
- `or_stop_after_time()`
- `and_stop_after_attempts()`
- `and_stop_after_time()`

### Conditions

- `on()`
- `retry_if_result()`
- `retry_if()`
- `any_condition()`
- `all_conditions()`
- `or_on()`
- `or_retry_if_result()`

### Delays

- `fixed_delay()`
- `no_delay()`
- `linear_delay()`
- `chain_delay()`
- `exponential_delay()`
- `random_delay()`
- `random_exponential_delay()`
- `jitter()`
- `add_delay()`
- `custom_delay()`
- `stateful_delay()`

### Exhaustion

- `raise_last()`
- `return_result()`
- `raise_on_result_exhausted()`
- `return_last_on_result_exhausted()`
- `fallback()`
- `fallback_value()`
- `on_exhausted_return()`
- `on_exhausted_return_value()`
- `on_exhausted_raise()`

### Retry budget

- `with_retry_budget()`
- `without_retry_budget()`

### Observability

- `on_event()`
- `on_before_attempt()`
- `on_success()`
- `on_failure()`
- `on_retry()`
- `on_giveup()`
- `debug()`
- `with_logging()`
- `with_structured_logging()`

### Guidance

- `warnings()`
- `doctor()`
- `simulate()`
- `timeline()`
- `preview()`
- `explain()`

### Execution

- `run()`
- `run_async()`
- `iter()`
- `async_iter()`
