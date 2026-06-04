# HTTP Retry

RetryFlow includes HTTP helpers without adding runtime dependencies.

They work with:

- response objects with `.status_code`
- dictionaries with `"status_code"`
- response objects with `.headers`
- dictionaries with `"headers"`

## Ready-to-use HTTP policy

```python
from retryflow import http_retry_policy

policy = http_retry_policy(
    attempts=5,
    statuses={429, 500, 502, 503, 504},
    respect_retry_after=True,
)
```

## Retry by status code

```python
from retryflow import RetryPolicy, retry_if_status

policy = (
    RetryPolicy()
    .attempts(5)
    .retry_if_result(retry_if_status({429, 500, 502, 503, 504}))
)
```

## Honor Retry-After

```python
from retryflow import RetryPolicy, retry_after_delay, retry_if_status

policy = (
    RetryPolicy()
    .attempts(5)
    .retry_if_result(retry_if_status({429, 503}))
    .stateful_delay(retry_after_delay(default=1.0, maximum=60.0))
)
```

The delay callback reads `state.last_value`, so it works naturally with result-based retry.

## Parse Retry-After manually

```python
from retryflow import parse_retry_after

seconds = parse_retry_after("120", default=1.0)
```

Supported formats:

- integer seconds: `Retry-After: 120`
- HTTP date values

Invalid or unusually large header values fall back to the provided default.

## Idempotency warning

Retrying HTTP requests is usually safe for idempotent methods:

- `GET`
- `HEAD`
- `PUT`
- `DELETE`
- `OPTIONS`

Be careful with:

- `POST`
- `PATCH`
- non-idempotent operations

RetryFlow does not block these operations because application context matters, but you should review them carefully.
