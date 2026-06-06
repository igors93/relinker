# Results and Statistics

Relinker can return the raw function value or a rich `RetryResult`.

## Return RetryResult

```python
from relinker import RetryPolicy

result = RetryPolicy().attempts(3).return_result().run(fetch_data)

print(result.succeeded)
print(result.failed)
print(result.attempt_count)
print(result.total_time)
```

## Summary

```python
print(result.summary())
```

The summary intentionally excludes returned values to keep logs small and safer.

## Dictionary and JSON output

```python
print(result.to_dict())
print(result.to_json(indent=2))
```

Returned values are excluded by default because they may be large, private, or not JSON-serializable.

Include explicitly:

```python
print(result.to_dict(include_value=True))
```

## Story

```python
print(result.story())
```

This gives a readable execution report for debugging, terminal output, or test failures.

## Per-function statistics

Decorated functions receive `retry_stats`.

```python
from relinker import network

@network()
def fetch_user() -> dict:
    return {"id": 1}

fetch_user()
print(fetch_user.retry_stats.to_dict())
```

Statistics are in-memory and attached to the decorated function.

Use `snapshot()` when you want an immutable view of the current counters:

```python
snapshot = fetch_user.retry_stats.snapshot()

print(snapshot.calls)
print(snapshot.average_attempts)
print(snapshot.success_rate)
```

Reset counters when a test or process-level reporting interval needs a clean
state:

```python
fetch_user.retry_stats.reset()
```

Statistics are in-memory, per decorated function, thread-safe for basic counter
updates, and dependency-free.
