# Async

Relinker supports async functions natively. The same policy semantics apply to
sync and async executions.

---

## Async decorator

```python
from relinker import retry

@retry(attempts=3, on=(TimeoutError,), delay=0)
async def fetch_user() -> dict:
    return await client.get("/users/1")
```

## Async policy

```python
from relinker import RetryPolicy

policy = RetryPolicy().attempts(3).on(TimeoutError)

@policy
async def fetch_user() -> dict:
    return await client.get("/users/1")
```

## Manual async run

Use `run_async()` when you need to call a coroutine function directly:

```python
result = await (
    RetryPolicy()
    .attempts(3)
    .on(TimeoutError)
    .return_result()
    .run_async(fetch_user)
)
```

`run()` is the synchronous entrypoint. Passing a coroutine function or an object
with `async __call__` to `run()` raises `InvalidRetryConfigError` before an
attempt starts. Use `await policy.run_async(...)` for asynchronous callables.

`run_async()` accepts any callable that returns an awaitable. This includes a
regular function used as an async factory:

```python
def fetch_user_factory():
    return fetch_user()

result = await policy.run_async(fetch_user_factory)
```

If the callable returns a regular value instead, `run_async()` raises
`InvalidRetryConfigError` after that first call. The usage error is not retried
and does not trigger delays, fallbacks, or retry-budget reservations. Use
`policy.run(...)` for a synchronous callable.

## Async context manager

Use `async_iter()` to retry a block of async code:

```python
policy = RetryPolicy().attempts(3).on(TimeoutError)

async for attempt in policy.async_iter(name="external_service"):
    async with attempt:
        response = await call_service()
        attempt.set_result(response)
```

---

## CancelledError behavior

`asyncio.CancelledError` (and `BaseException` subclasses in general) are not
treated as retry-eligible failures. They propagate immediately, bypassing the
retry condition and exhaustion logic.

This is intentional: cancellation is a control flow signal, not an application
error. Catching and retrying a `CancelledError` would interfere with task
cancellation, cooperative shutdown, and timeout machinery like
`asyncio.wait_for`.

If your function raises `CancelledError`, Relinker propagates it without
attempting a retry and without applying a fallback.

---

## Async event handlers are not supported

Event handlers must be synchronous functions. Passing an async function as a
handler raises `InvalidRetryConfigError` immediately:

```python
async def on_retry(event):
    await send_metric(event)

# Raises InvalidRetryConfigError.
policy = RetryPolicy().on_retry(on_retry)
```

**Why:** Relinker supports both sync and async execution paths. A handler runs
inline before sleeping. An async handler could only be awaited on an async
path, but Relinker also supports sync execution where no event loop is present.
Attempting to run a coroutine on a sync path would require creating a new loop,
which is incompatible with applications that already have one.

**Alternative:** use a synchronous handler that queues work for your async
infrastructure:

```python
import asyncio
import queue

_retry_events: queue.Queue = queue.Queue()

def record_retry(event) -> None:
    _retry_events.put_nowait({
        "name": event.name,
        "attempt": event.attempt_number,
        "delay": event.delay,
    })

policy = RetryPolicy().attempts(3).on(TimeoutError).on_retry(record_retry)
```

Consume `_retry_events` from a background task in your async application.

Keep handlers fast. A handler runs inline before each sleep; slow handlers add
latency to every retry.

---

## Custom async sleep

Relinker uses `asyncio.sleep` by default. Provide a custom async sleep for
alternative runtimes or testing:

```python
async def custom_sleep(seconds: float) -> None:
    await my_runtime.sleep(seconds)

policy = RetryPolicy().with_sleep(
    lambda seconds: None,     # sync no-op for sync paths
    async_sleep=custom_sleep,
)
```

The core package does not depend on Trio, AnyIO, or any specific async runtime.
This lets you integrate the runtime you prefer.

---

## Testing async retry

Use `for_testing()` to remove real sleep from async tests:

```python
async def test_retries_on_timeout():
    calls = 0

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError()
        return "ok"

    policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(5).for_testing()
    result = await policy.run_async(flaky)
    assert result == "ok"
    assert calls == 2
```

---

## Related pages

- [Testing retry code](testing.md) — keep tests fast and deterministic
- [Policy builder](policy-builder.md) — full method reference
- [Retry lifecycle](../concepts/retry-lifecycle.md) — event order and execution model
- [Troubleshooting](troubleshooting.md) — async handler rejection and other symptoms
