# HTTP helpers

RetryFlow includes optional HTTP helpers in `retryflow.http`. They require no external dependencies and work with any HTTP library or custom response object.

## Import

```python
from retryflow.http import (
    should_retry_http_status,
    retry_if_status,
    retry_after_delay,
    parse_retry_after,
)
```

## should_retry_http_status

Returns `True` when a status code is in a set of retryable codes:

```python
if should_retry_http_status(response.status_code, {429, 500, 502, 503, 504}):
    raise RetryableError()
```

## retry_if_status

Returns a predicate for use with `.retry_if_result()`. Supports objects with a `.status_code` attribute and dicts with a `"status_code"` key. Unknown objects return `False`.

```python
from retryflow import RetryPolicy
from retryflow.http import retry_if_status, retry_after_delay

RETRYABLE = {429, 500, 502, 503, 504}

policy = (
    RetryPolicy()
    .attempts(5)
    .retry_if_result(retry_if_status(RETRYABLE))
    .stateful_delay(retry_after_delay(default=1.0, maximum=60.0))
    .return_result()
)

result = policy.run(lambda: http_client.get("/api/data"))
```

## retry_after_delay

Returns a **state-aware** delay callback for use with `.stateful_delay()`. It reads the `Retry-After` header from the last response when available.

```python
from retryflow.http import retry_after_delay

policy = (
    RetryPolicy()
    .attempts(5)
    .retry_if_result(retry_if_status({429, 503}))
    .stateful_delay(retry_after_delay(default=1.0, maximum=60.0))
)
```

### How it works

1. Before each sleep, the executor puts the last returned value in `state.last_value`.
2. `retry_after_delay` reads `state.last_value` and looks for a response object.
3. If the response has a `Retry-After` header, it parses it and returns that value.
4. If the header is missing or unparseable, it returns the `default` value.
5. The result is always capped by `maximum` when provided.
6. The result is never negative.

### Supported response formats

```python
# Object with .headers attribute
class Response:
    headers = {"Retry-After": "30"}

# Dict with "headers" key
response = {"status_code": 429, "headers": {"Retry-After": "30"}}
```

Header lookup is case-insensitive: `Retry-After`, `retry-after`, and `RETRY-AFTER` all work.

### Important: requires retry_if_result

`retry_after_delay` reads `state.last_value`. For this value to be set, you need a result-based retry condition (`retry_if_result`). With exception-based retry, `state.last_value` will be `None` and the callback always returns the default.

```python
# Works: last response is in state.last_value
policy = (
    RetryPolicy()
    .retry_if_result(retry_if_status({429, 503}))
    .stateful_delay(retry_after_delay(default=1.0))
)

# Default used: exception-based retry has no response in state
policy = (
    RetryPolicy()
    .on(ConnectionError)
    .stateful_delay(retry_after_delay(default=1.0))  # always uses 1.0
)
```

### requires .stateful_delay()

`retry_after_delay` is designed for `stateful_delay()`, not `custom_delay()`.

```python
# Correct
policy.stateful_delay(retry_after_delay(default=1.0))

# Wrong: custom_delay expects Callable[[int], float]
policy.custom_delay(retry_after_delay(default=1.0))  # type error
```

## parse_retry_after

Parses a `Retry-After` header value into seconds:

```python
parse_retry_after("120")           # 120.0 (integer seconds)
parse_retry_after("30")            # 30.0
parse_retry_after("invalid", 5.0)  # 5.0 (fallback)
parse_retry_after("Wed, 04 Jun 2026 12:00:00 GMT")  # seconds until that time
```

Negative values are clamped to `0.0`. Invalid values fall back to the `default` argument.

## Idempotency

Retrying HTTP requests is safe for idempotent methods (GET, HEAD, PUT, DELETE). Retrying POST, PATCH, or non-idempotent methods can cause duplicate side effects. RetryFlow does not block non-idempotent retries — this is an application-level concern. Document it in your code when retrying non-idempotent operations.
