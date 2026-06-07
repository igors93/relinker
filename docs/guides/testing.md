# Testing Retry Code

Retry code can make tests slow if it sleeps for real. Relinker lets you inject custom sleep functions.

## Disable sleep in tests

The simplest way to disable sleep is the built-in `for_testing()` method:

```python
from relinker import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(3)
    .fixed_delay(10)
    .for_testing()  # replaces sync and async sleep with no-ops
)
```

`for_testing()` returns a new policy and preserves all other settings (attempts, conditions,
delays, event handlers). It is chainable and can be called at any point in the builder chain.

> **Note:** `max_time` and retry-budget windows still use real wall-clock time. They will
> behave as if no time passes between retries, which may cause `max_time`-based exhaustion
> to behave differently than in production.

`doctor()` reports this combination explicitly when a policy created with
`for_testing()` also uses `max_time()`.

For lower-level control, you can inject custom sleep functions directly:

```python
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
