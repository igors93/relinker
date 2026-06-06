# RetryState

`RetryState` is an immutable snapshot of a retry execution at a specific point in time.

## Where you see it

RetryState appears in two places:

1. **Event handlers** — every `RetryEvent` includes an optional `state` field.
2. **Stateful delay callbacks** — the callback passed to `policy.stateful_delay()` receives a `RetryState`.

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `function_name` | `str` | Name of the wrapped function |
| `attempt_number` | `int` | One-based current attempt number |
| `started_at` | `float` | Monotonic timestamp when the whole execution started |
| `elapsed` | `float` | Seconds elapsed since execution started |
| `attempts` | `tuple[AttemptRecord, ...]` | Attempts recorded before this snapshot |
| `last_value` | `Any` | Last returned value, when available |
| `last_error` | `BaseException \| None` | Last raised exception, when available |
| `next_delay` | `float \| None` | Computed delay before the next attempt (set on `before_sleep` events) |
| `retry_cause` | `"exception" \| "result" \| None` | What triggered this retry |
| `will_retry` | `bool` | True when Relinker will make another attempt |
| `will_stop` | `bool` | True when the stop strategy fired |

## Properties

| Property | Returns | Description |
|----------|---------|-------------|
| `attempt_count` | `int` | Number of recorded attempts in `attempts` |
| `failed_attempts` | `int` | Attempts in `attempts` that raised an exception |
| `successful_attempts` | `int` | Attempts in `attempts` that returned a value |
| `last_attempt()` | `AttemptRecord \| None` | Most recent recorded attempt, or None |
| `has_error` | `bool` | True when `last_error` is not None |
| `has_value` | `bool` | True when `last_error` is None and `last_value` is not None |

## Using state in event handlers

```python
from relinker import RetryPolicy

def on_failure(event):
    state = event.state
    if state is None:
        return
    print(f"Attempt {state.attempt_number} failed after {state.elapsed:.2f}s")
    print(f"  Error: {state.last_error}")
    print(f"  Will retry: {state.will_retry}")

policy = RetryPolicy().attempts(5).on(TimeoutError).on_event("after_failure", on_failure)
```

## Using state in stateful delays

```python
from relinker import RetryPolicy, RetryState

def adaptive_delay(state: RetryState) -> float:
    # Back off more aggressively after many failures
    if state.failed_attempts > 3:
        return 5.0
    return float(state.attempt_number) * 0.5

policy = RetryPolicy().attempts(8).on(TimeoutError).stateful_delay(adaptive_delay)
```

## State-aware HTTP Retry-After delay

```python
from relinker import RetryPolicy
from relinker.http import retry_if_status, retry_after_delay

RETRYABLE = {429, 500, 502, 503, 504}

policy = (
    RetryPolicy()
    .attempts(5)
    .retry_if_result(retry_if_status(RETRYABLE))
    .stateful_delay(retry_after_delay(default=1.0, maximum=60.0))
)
```

Here `state.last_value` holds the last response returned by the function, and
`retry_after_delay` reads its `Retry-After` header before each sleep.

## What data is safe to log

`RetryState` contains:

- Safe to log: `attempt_number`, `elapsed`, `will_retry`, `will_stop`, `retry_cause`,
  `attempt_count`, `failed_attempts`, `function_name`
- May be sensitive: `last_value` — this is the actual return value from your function,
  which could contain tokens, passwords, or private data
- Usually safe: `last_error` — error messages are typically not sensitive, but
  review them before logging in production

```python
def safe_log_handler(event):
    state = event.state
    if state is None:
        return
    # Log only structural metadata, not the value
    print({
        "attempt": state.attempt_number,
        "elapsed": round(state.elapsed, 3),
        "will_retry": state.will_retry,
        "error": type(state.last_error).__name__ if state.last_error else None,
    })
```

## Immutability

`RetryState` is frozen — no field can be changed after creation. This means event
handlers and delay callbacks can read it safely without needing to copy it.
