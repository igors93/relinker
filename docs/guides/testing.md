# Testing Retry Code

Retry code can make tests slow if it sleeps for real. Relinker lets you inject custom sleep functions.

## Disable sleep in tests

```python
from relinker import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(3)
    .fixed_delay(10)
    .with_sleep(lambda seconds: None)
)
```

The policy still behaves like it has a 10-second delay, but tests do not wait.

## Capture requested sleeps

```python
sleeps: list[float] = []

policy = RetryPolicy().attempts(3).fixed_delay(1).with_sleep(sleeps.append)
```

Now your test can assert:

```python
assert sleeps == [1, 1]
```

## Async sleep in tests

```python
async def fake_async_sleep(seconds: float) -> None:
    return None

policy = RetryPolicy().attempts(3).with_sleep(
    lambda seconds: None,
    async_sleep=fake_async_sleep,
)
```

## Test the policy, not only the function

Use diagnostics in tests:

```python
assert not policy.doctor().ok or policy.doctor().risk_level in {"warning", "risky"}
```

For production policies, consider snapshotting `policy.explain()` or checking for specific warnings.
