# Policy Builder

`RetryPolicy` is the main object in Relinker. It is an immutable builder: every method returns a new policy instead of mutating the original.

```python
from relinker import RetryPolicy

base = RetryPolicy().attempts(3)
network_policy = base.on(TimeoutError).exponential_delay(base=1)
database_policy = base.on(ConnectionError).fixed_delay(0.2)
```

The original `base` policy is not changed.

## Stop strategies

```python
RetryPolicy().attempts(3)
RetryPolicy().max_time(30)
RetryPolicy().forever()
```

Use `forever()` carefully. It is valid, but Relinker will warn because retrying forever can be dangerous without cancellation, delays, or external supervision.

## Retry conditions

Retry by exception:

```python
RetryPolicy().on(TimeoutError, ConnectionError)
```

Retry by result:

```python
RetryPolicy().retry_if_result(lambda response: response.status_code >= 500)
```

Retry with a custom callback:

```python
RetryPolicy().retry_if(lambda error, value: error is not None)
```

## Delays

```python
RetryPolicy().fixed_delay(1)
RetryPolicy().linear_delay(start=0.5, step=0.5, maximum=5)
RetryPolicy().exponential_delay(base=1, factor=2, maximum=30)
RetryPolicy().random_delay(minimum=0, maximum=1)
RetryPolicy().random_exponential_delay(base=0.25, maximum=10)
RetryPolicy().chain_delay([0.1, 0.5, 1, 2])
RetryPolicy().custom_delay(lambda attempt: attempt * 0.5)
```

Add jitter to another delay:

```python
RetryPolicy().exponential_delay(base=1, maximum=30).jitter(maximum=0.5)
```

## State-aware delay

Use `stateful_delay()` when the delay depends on the retry state.

```python
from relinker import RetryPolicy, RetryState

def delay_from_state(state: RetryState) -> float:
    if state.last_error is not None:
        return min(state.attempt_number, 10)
    return 1

policy = RetryPolicy().attempts(5).stateful_delay(delay_from_state)
```

This is useful for HTTP `Retry-After`, rate limits, and custom backoff rules.

## Exhausted behavior

When retries are exhausted, choose what happens explicitly:

```python
RetryPolicy().raise_last()
RetryPolicy().return_result()
RetryPolicy().fallback(lambda result: {"status": "offline"})
RetryPolicy().fallback_value({"status": "offline"})
RetryPolicy().on_exhausted_raise(RuntimeError)
RetryPolicy().raise_on_result_exhausted()
```

## Event hooks

```python
policy = (
    RetryPolicy()
    .attempts(3)
    .on_retry(lambda event: print(event.delay))
    .on_giveup(lambda event: print("giving up"))
)
```

Available friendly shortcuts:

- `on_before_attempt()`
- `on_success()`
- `on_failure()`
- `on_retry()`
- `on_giveup()`
