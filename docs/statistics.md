# Statistics

Decorated functions automatically receive in-memory retry statistics.

```python
from retryflow import retry

@retry(attempts=3)
def fetch_data() -> str:
    return "ok"

fetch_data()
fetch_data()

print(fetch_data.retry_stats.to_dict())
```

Example output:

```python
{
    "calls": 2,
    "successes": 2,
    "failures": 0,
    "exhausted": 0,
    "total_attempts": 2,
    "total_time": 0.001,
    "average_attempts": 1.0,
    "success_rate": 1.0,
    "failure_rate": 0.0,
}
```

## Snapshot

Use `snapshot()` when you want an immutable view.

```python
snapshot = fetch_data.retry_stats.snapshot()

print(snapshot.calls)
print(snapshot.average_attempts)
print(snapshot.success_rate)
```

## Reset

```python
fetch_data.retry_stats.reset()
```

Statistics are in-memory, per decorated function, thread-safe for basic counter
updates, and dependency-free.
