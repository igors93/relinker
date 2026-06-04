# Observability

RetryFlow exposes lightweight observability without requiring external logging, metrics, or tracing libraries.

## Standard logging

```python
import logging
from retryflow import RetryPolicy

logging.basicConfig(level=logging.INFO)

policy = (
    RetryPolicy()
    .attempts(3)
    .on(TimeoutError)
    .fixed_delay(1)
    .with_logging(level=logging.INFO)
)
```

## Structured logging

```python
policy = (
    RetryPolicy()
    .attempts(3)
    .on(TimeoutError)
    .with_structured_logging()
)
```

Structured logging emits compact JSON strings.

By default, RetryFlow does not include exception messages in structured logs because exception messages can contain sensitive information.

Enable only when safe:

```python
policy = RetryPolicy().with_structured_logging(include_error_message=True)
```

## Event hooks

Use event hooks when you want custom behavior.

```python
from retryflow import RetryEvent, RetryPolicy

def capture_retry(event: RetryEvent) -> None:
    print(event.name, event.attempt_number, event.delay)

policy = RetryPolicy().attempts(3).on_retry(capture_retry)
```

## Event names

| Friendly method | Event name | When it runs |
|---|---|---|
| `on_before_attempt()` | `before_attempt` | Before each attempt |
| `on_success()` | `after_success` | After an accepted success |
| `on_failure()` | `after_failure` | After a failed attempt |
| `on_retry()` | `before_sleep` | Before sleeping for another attempt |
| `on_giveup()` | `after_giveup` | When RetryFlow gives up |

## RetryState

Events include a `RetryState` snapshot when available. It can contain:

- function name
- attempt number
- elapsed time
- recorded attempts
- last value
- last error
- next delay
- retry cause
- whether it will retry
- whether it will stop
