# API Reference

This is a practical overview of the public API.

## Main imports

```python
from retryflow import RetryPolicy, retry
from retryflow import fast, network, database, patient, background_job
```

## RetryPolicy

### Stop methods

```python
RetryPolicy().attempts(3)
RetryPolicy().max_time(30)
RetryPolicy().forever()
RetryPolicy().or_stop_after_time(30)
RetryPolicy().or_stop_after_attempts(5)
```

### Retry conditions

```python
RetryPolicy().on(TimeoutError, ConnectionError)
RetryPolicy().retry_if_result(lambda value: value is None)
RetryPolicy().retry_if(lambda error, value: True)
RetryPolicy().or_on(OSError)
RetryPolicy().or_retry_if_result(lambda value: value == "retry")
```

### Delay methods

```python
RetryPolicy().no_delay()
RetryPolicy().fixed_delay(1)
RetryPolicy().linear_delay(start=1, step=2, maximum=10)
RetryPolicy().chain_delay([0.1, 0.5, 1, 2])
RetryPolicy().exponential_delay(base=1, maximum=30)
RetryPolicy().random_delay(minimum=0, maximum=1)
RetryPolicy().random_exponential_delay(base=1, maximum=30)
RetryPolicy().jitter(maximum=0.5)
RetryPolicy().custom_delay(lambda attempt: attempt * 0.5)
```

### Exhausted behavior

```python
RetryPolicy().return_result()
RetryPolicy().fallback_value(None)
RetryPolicy().fallback(lambda result: None)
RetryPolicy().on_exhausted_raise(RuntimeError)
RetryPolicy().raise_on_result_exhausted()
```

### Diagnostics

```python
RetryPolicy().warnings()
RetryPolicy().simulate(attempts=5)
RetryPolicy().timeline(attempts=5)
RetryPolicy().explain()
```

### Execution

```python
policy.run(function, *args, **kwargs)
await policy.run_async(function, *args, **kwargs)
```

### Decorator

```python
@RetryPolicy().attempts(3)
def task() -> str:
    return "ok"
```

Decorated functions receive:

```python
task.retry_stats
task.retry_policy
task.with_policy
```

## retry decorator

```python
@retry
def task() -> str:
    return "ok"

@retry(attempts=5, delay=1, on=(TimeoutError,))
def call_api() -> str:
    return "response"
```

Use `@retry` for simple cases. Use `RetryPolicy` or presets for advanced behavior.
