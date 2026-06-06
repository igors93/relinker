# Context Manager Usage

The decorator API is the easiest way to retry a function. The context manager API is useful when you want to retry a block of code without extracting it into a separate function.

## Basic block retry

```python
from relinker import RetryPolicy

policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(1)

for attempt in policy:
    with attempt:
        call_external_service()
```

## Result-based retry in a block

Use `set_result()` when retry depends on a returned value.

```python
from relinker import RetryPolicy, retry_if_status

policy = RetryPolicy().attempts(3).retry_if_result(retry_if_status({503}))

for attempt in policy:
    with attempt:
        response = attempt.set_result(call_api())
```

## Async block retry

```python
from relinker import RetryPolicy

policy = RetryPolicy().attempts(3).on(TimeoutError)

async for attempt in policy:
    async with attempt:
        await call_external_service()
```

## Accessing the result

The iterator stores the final result:

```python
iterator = policy.iter(name="manual_block")

for attempt in iterator:
    with attempt:
        call_external_service()

print(iterator.result)
```

## Recommendation

Prefer decorators or `policy.run()` for most cases. Use context managers when the code truly needs to remain inline.
