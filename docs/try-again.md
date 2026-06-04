# TryAgain

`TryAgain` is an explicit retry signal you can raise from inside a wrapped function to request another attempt, regardless of the configured retry condition.

## Basic usage

```python
from retryflow import RetryPolicy, TryAgain

def task():
    result = call_service()
    if result == "pending":
        raise TryAgain("not ready yet")
    return result

policy = RetryPolicy().attempts(10).on(ConnectionError)
result = policy.run(task)
```

In this example, `TryAgain` retries the function even though `ConnectionError` is the only configured retry type.

## Why TryAgain

Normal retry conditions check the exception type or the returned value. Sometimes you want to trigger a retry based on business logic — for example, when a service returns "pending" instead of raising an exception.

`TryAgain` separates the retry decision from the exception filtering: your function decides when to retry, and the policy controls how many times and how long to wait.

## Behaviour

- `TryAgain` bypasses the condition check — it always requests another attempt.
- `TryAgain` still respects the stop strategy. When attempts are exhausted, the last `TryAgain` is used as the error.
- `TryAgain` preserves its message: `str(TryAgain("not ready"))` returns `"not ready"`.
- `TryAgain` does not affect `KeyboardInterrupt` or `SystemExit` — they are never caught.
- Works with sync functions, async functions, and context manager blocks.

## Exhaustion behaviour

When attempts are exhausted due to `TryAgain`:

```python
# Return the result object (includes the error)
result = policy.return_result().run(task)
assert isinstance(result.error, TryAgain)
assert result.exhausted

# Use a fallback value
result = policy.fallback(lambda r: "default").run(task)

# Raise a custom exception
from retryflow import RetryExhaustedError
policy.on_exhausted_raise(RetryExhaustedError).run(task)
```

## Async support

`TryAgain` works identically in async functions:

```python
async def check_job():
    status = await fetch_status()
    if status != "done":
        raise TryAgain("job still running")
    return status

result = await policy.run_async(check_job)
```

## Context manager blocks

`TryAgain` works in context manager blocks:

```python
for attempt in policy:
    with attempt:
        status = call_service()
        if status == "pending":
            raise TryAgain("not ready")
```

When `TryAgain` exhausts in a context manager, the exception propagates (consistent with how regular exceptions behave on exhaustion in blocks).

## Import

```python
from retryflow import TryAgain
```

Or explicitly from the exceptions module:

```python
from retryflow.exceptions import TryAgain
```
