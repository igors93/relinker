# HTTP helpers

RetryFlow includes optional HTTP helpers in `retryflow.http`. These do not add any runtime dependencies and work with any HTTP library.

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
from retryflow.http import should_retry_http_status

if should_retry_http_status(response.status_code, {429, 500, 502, 503, 504}):
    raise RetryableError()
```

## retry_if_status

Returns a predicate for use with `.retry_if_result()`. Supports objects with a `.status_code` attribute and dicts with a `"status_code"` key. Unknown objects return `False`.

```python
from retryflow import RetryPolicy
from retryflow.http import retry_if_status

RETRYABLE = {429, 500, 502, 503, 504}

policy = (
    RetryPolicy()
    .attempts(5)
    .retry_if_result(retry_if_status(RETRYABLE))
    .exponential_delay(base=0.5, maximum=10)
    .return_result()
)

result = policy.run(lambda: http_client.get("/api/data"))
```

Works with any response-like object:

```python
# Objects with .status_code
retry_if_status({503})(response_object)

# Dicts with "status_code" key
retry_if_status({503})({"status_code": 503})

# Unknown objects return False (no retry)
retry_if_status({503})("something else")  # False
```

## retry_after_delay

Returns a custom delay callback that always returns a fixed default value. Useful when you want consistent delays for HTTP retries without implementing dynamic header parsing.

```python
from retryflow.http import retry_after_delay

policy = (
    RetryPolicy()
    .attempts(5)
    .custom_delay(retry_after_delay(default=2.0, maximum=30.0))
)
```

### Limitation: Retry-After header

The current delay strategy architecture passes only the attempt number to delay callbacks — not the last response. If you need to honour a dynamic `Retry-After` response header, use the `before_sleep` event to read the header value and coordinate with a `custom_delay` callback via shared state:

```python
last_retry_after = [0.0]

def capture_retry_after(event):
    response = event.state.last_value  # the last returned response
    if isinstance(response, dict):
        header = response.get("retry_after", "")
        last_retry_after[0] = parse_retry_after(str(header), default=1.0)

def dynamic_delay(attempt):
    return last_retry_after[0] or 1.0

policy = (
    RetryPolicy()
    .attempts(5)
    .custom_delay(dynamic_delay)
    .on_event("before_sleep", capture_retry_after)
)
```

## parse_retry_after

Parses a `Retry-After` header value into a delay in seconds:

```python
from retryflow.http import parse_retry_after

# Integer seconds
parse_retry_after("120")          # 120.0
parse_retry_after("  60  ")       # 60.0

# HTTP date
parse_retry_after("Wed, 04 Jun 2026 12:00:00 GMT")  # seconds until that time

# Invalid fallback
parse_retry_after("invalid", default=5.0)  # 5.0
```

Negative values are clamped to zero. Invalid values fall back to the `default` parameter (default `0.0`).

## Idempotency

Retrying HTTP requests is safe for idempotent methods (GET, HEAD, PUT, DELETE). Retrying POST, PATCH, or non-idempotent methods can cause duplicate side effects. RetryFlow does not block non-idempotent retries — this is an application-level concern — but it documents the concern here so users can decide.
