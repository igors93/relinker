# Exhaustion behavior

Exhaustion means an outcome requested another attempt, but the stop strategy or
time budget did not allow one. Relinker keeps this separate from a non-retryable
exception, which is propagated immediately.

## Exception-based exhaustion

The default is to re-raise the last original exception:

```python
policy = RetryPolicy().attempts(3).on(TimeoutError)
```

You can choose another final behavior:

```python
RetryPolicy().return_result()
RetryPolicy().fallback_value({"status": "offline"})
RetryPolicy().fallback(lambda result: result.summary())
RetryPolicy().on_exhausted_raise(ServiceUnavailableError)
RetryPolicy().raise_last()
```

## Result-based exhaustion

When retries are caused by rejected return values, the default is to return the
last value:

```python
policy = (
    RetryPolicy()
    .attempts(3)
    .retry_if_result(lambda value: value == "waiting")
)
```

Use `raise_on_result_exhausted()` when exhaustion must be explicit:

```python
policy = policy.raise_on_result_exhausted()
```

Use `return_last_on_result_exhausted()` to restore the default.

## Last configuration wins

Final behaviors are mutually exclusive. The last behavior method called expresses
the user's intent.

| Policy chain | Final behavior |
|---|---|
| `fallback_value("safe").raise_last()` | Re-raise the original exception |
| `raise_last().fallback_value("safe")` | Return `"safe"` |
| `fallback_value("safe").return_result()` | Return `RetryResult` |
| `return_result().fallback_value("safe")` | Return `"safe"` |
| `fallback_value("safe").on_exhausted_raise(ValueError)` | Raise `ValueError` |
| `on_exhausted_raise(ValueError).raise_last()` | Re-raise the original exception |

This rule is protected by contract and regression tests.

## Choosing a behavior

Use `raise_last()` when callers already understand the original exception.

Use `fallback()` or `fallback_value()` for deliberate graceful degradation.
Fallbacks should return values that callers can distinguish from a normal result.

Use `on_exhausted_raise()` to translate infrastructure failures into a stable
domain exception.

Use `return_result()` when callers need attempts, timing, errors, and exhaustion
metadata instead of a raw value or exception.

## Context managers

Retry-block iterators expose their final `result`. A configured fallback is also
available through the iterator outcome. Sync and async context managers follow
the same exhaustion contract as direct execution.

## Non-retryable errors

An exception that does not match the retry condition is not exhausted. It is
propagated immediately and no fallback is applied merely because a fallback is
configured for retry exhaustion.
