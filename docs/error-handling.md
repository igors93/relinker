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

if result.failed:
    print(result.story())
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

## Behavior precedence

RetryFlow keeps behavior explicit. The last behavior method you call usually
expresses your intention.

Examples:

```python
RetryPolicy().fallback_value("safe").return_result()
```

This returns `RetryResult`, because `return_result()` is configured last.

```python
RetryPolicy().return_result().fallback_value("safe")
```

This returns `"safe"` when attempts are exhausted, because `fallback_value()` is
configured last and disables `return_result()`.

Recommended rule:

- Use `return_result()` when you want inspection.
- Use `fallback()` or `fallback_value()` when you want graceful degradation.
- Use `on_exhausted_raise()` when callers should handle a domain-specific error.

## Result-based exhaustion

When retry is caused by returned values, you can choose whether to return the
last value or raise.

```python
policy = (
    RetryPolicy()
    .attempts(3)
    .retry_if_result(lambda value: value is None)
    .raise_on_result_exhausted()
)
```
