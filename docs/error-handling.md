# Error Handling

RetryFlow gives you multiple ways to control what happens when retry attempts are
exhausted.

## Default behavior

For exception-based retry, RetryFlow raises the last original exception.

```python
policy = RetryPolicy().attempts(3).on(TimeoutError)
```

## Return RetryResult

```python
result = (
    RetryPolicy()
    .attempts(3)
    .on(TimeoutError)
    .return_result()
    .run(call_api)
)
```

## Return a fallback value

```python
policy = (
    RetryPolicy()
    .attempts(3)
    .on(TimeoutError)
    .fallback_value({"status": "unavailable"})
)
```

## Return a fallback from a callback

```python
def fallback(result):
    print(result.story())
    return None

policy = RetryPolicy().attempts(3).on(TimeoutError).fallback(fallback)
```

## Raise a custom exception

```python
class ServiceUnavailableError(RuntimeError):
    pass

policy = (
    RetryPolicy()
    .attempts(3)
    .on(TimeoutError)
    .on_exhausted_raise(ServiceUnavailableError)
)
```

## Raise from a factory

```python
def make_error(result):
    return RuntimeError(f"Failed after {result.attempt_count} attempts")

policy = RetryPolicy().attempts(3).on(TimeoutError).on_exhausted_raise(make_error)
```
