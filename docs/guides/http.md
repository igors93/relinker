# HTTP Retry

Relinker includes HTTP helpers without adding runtime dependencies.

They work with:

- response objects with `.status_code`
- dictionaries with `"status_code"`
- response objects with `.headers`
- dictionaries with `"headers"`
- opt-in transport exceptions such as timeouts and connection failures

## Ready-to-use HTTP policy

```python
from relinker import DEFAULT_RETRYABLE_TRANSPORT_EXCEPTIONS, http_retry_policy

policy = http_retry_policy(
    attempts=5,
    statuses={429, 500, 502, 503, 504},
    transport_exceptions=DEFAULT_RETRYABLE_TRANSPORT_EXCEPTIONS,
    respect_retry_after=True,
)
```

`transport_exceptions` defaults to an empty tuple in the `1.x` series. This
preserves existing result-based behavior: a `TimeoutError` or `ConnectionError`
is retried only when you opt in explicitly.

`DEFAULT_RETRYABLE_TRANSPORT_EXCEPTIONS` includes `OSError` for compatibility
with the existing broad transport recipe. Because `OSError` also covers local
operating-system failures, `doctor()` reports `broad_os_error` when that bundle
is used. Prefer a narrower tuple when the client exposes specific exceptions:

```python
policy = http_retry_policy(
    transport_exceptions=(TimeoutError, ConnectionError),
)
```

The warning is advisory. It does not change which failures are retried.

## Retry by status code

```python
from relinker import RetryPolicy, retry_if_status

policy = (
    RetryPolicy()
    .attempts(5)
    .retry_if_result(retry_if_status({429, 500, 502, 503, 504}))
)
```

## Honor Retry-After

```python
from relinker import RetryPolicy, retry_after_delay, retry_if_status

policy = (
    RetryPolicy()
    .attempts(5)
    .retry_if_result(retry_if_status({429, 503}))
    .stateful_delay(retry_after_delay(default=1.0, maximum=60.0))
)
```

The delay callback reads `state.last_value`, so it works naturally with result-based retry.

For transport exceptions there is no response object, so `http_retry_policy()`
uses `default_delay` for that retry.

## Parse Retry-After manually

```python
from relinker import parse_retry_after

seconds = parse_retry_after("120", default=1.0)
```

Supported formats:

- integer seconds: `Retry-After: 120`
- HTTP date values

Invalid header values fall back to the provided default. Valid large header
values are capped by the configured maximum.

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

Relinker does not block these operations because application context matters, but you should review them carefully.
