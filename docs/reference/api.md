# API Reference

The stable root import surface is `relinker.__all__`. All exports listed here
are stable from `1.0.0` and covered by the compatibility and deprecation policy.
For compatibility guarantees and API tiers, see the
[Compatibility policy](compatibility.md). For upgrade guidance, see
[Migrating to 1.0](../guides/migrating-to-1.0.md).

For behavioral details, see [Retry lifecycle](../concepts/retry-lifecycle.md) and
[Exhaustion behavior](../concepts/exhaustion.md).

## Root package exports

### Core execution

| Name | Purpose |
|---|---|
| `retry` | Simple decorator entry point. |
| `RetryPolicy` | Fluent policy builder. |
| `RetryBudget` | Shared process-local retry capacity. |
| `RetryResult` | Rich execution result. |
| `RetryState` | Immutable runtime state snapshot. |
| `RetryWrappedFunction` | Type alias for a wrapped retry callable. |

### Context managers

| Name | Purpose |
|---|---|
| `RetryAttemptContext` | Synchronous retry attempt context manager. |
| `AsyncRetryAttemptContext` | Asynchronous retry attempt context manager. |

The block iterators are documented module exports in `relinker.context`, not
root package exports.

### Statistics and diagnostics

| Name | Purpose |
|---|---|
| `RetryStats` | Mutable retry statistics accumulator. |
| `RetryStatsSnapshot` | Immutable retry statistics snapshot. |
| `PolicyWarning` | Advisory warning about a policy. |
| `PolicyHealthReport` | Doctor report for a policy. |
| `RetrySimulation` | Simulated retry timeline. |
| `RetrySimulationAttempt` | One simulated attempt. |

### Exceptions and control flow

| Name | Purpose |
|---|---|
| `RelinkerError` | Base Relinker exception. |
| `InvalidRetryConfigError` | Invalid configuration. |
| `RetryExhaustedError` | Retry exhaustion raised explicitly. |
| `TryAgain` | Explicit retry signal. |

### HTTP

| Name | Purpose |
|---|---|
| `DEFAULT_RETRYABLE_STATUSES` | Default retryable HTTP statuses. |
| `MAX_RETRY_AFTER_SECONDS` | Maximum accepted `Retry-After` delay. |
| `should_retry_http_status` | Check if a status should retry. |
| `retry_if_status` | Build a result predicate for HTTP responses. |
| `retry_after_delay` | Build a state-aware delay from `Retry-After`. |
| `parse_retry_after` | Parse a `Retry-After` header. |
| `http_retry_policy` | Ready-to-use HTTP retry policy. |

### Presets

| Name | Purpose |
|---|---|
| `fast` | Small and quick retry policy. |
| `network` | Network and external API calls. |
| `database` | Database-like transient failures. |
| `patient` | Slower retry policy for operations that can wait. |
| `background_job` | Background workers and scheduled jobs. |

## Documented module exports

The documented public exports of `relinker.context` are:

```python
from relinker.context import (
    AsyncRetryAttemptContext,
    AsyncRetryBlockIterator,
    RetryAttemptContext,
    RetryBlockIterator,
)
```

`RetryAttemptContext` and `AsyncRetryAttemptContext` are also root package
exports. `RetryBlockIterator` and `AsyncRetryBlockIterator` remain documented
exports of `relinker.context`.

Underscore-prefixed modules and helpers are internal. In particular,
`relinker.context._shared` is not public API.

## Package metadata

`relinker.__version__` is available as package metadata. It is intentionally not
part of `relinker.__all__`, so it is not included in the root star-import API.

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
