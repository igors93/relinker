# Observability

Relinker exposes lightweight observability without requiring external logging, metrics, or tracing libraries.

## Standard logging

```python
import logging
from relinker import RetryPolicy

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

By default, Relinker does not include exception messages in structured logs because exception messages can contain sensitive information.

Enable only when safe:

```python
policy = RetryPolicy().with_structured_logging(include_error_message=True)
```

The built-in logging handlers are observational and use isolated event handler
failure mode. If a logging sink raises a normal `Exception`, Relinker reports
the handler failure through the `relinker.events` logger and continues the retry
flow.

## RetryResult output

`RetryResult.summary()` excludes exception messages and is suitable for compact
logging. Detailed output preserves messages by default for compatibility. When a
result may be written to logs or telemetry, exclude messages explicitly:

```python
logger.info(
    "retry_result=%s",
    result.to_json(include_error_message=False),
)
```

The same option is available for dictionary and human-readable output:

```python
data = result.to_dict(include_error_message=False)
text = result.story(include_error_message=False)
```

Exception types and attempt metadata remain available. Redaction changes only the
generated representation; it does not remove the original exception objects from
the result.

## Event hooks

Use event hooks when you want custom behavior.

```python
from relinker import RetryPolicy
from relinker.event import RetryEvent

def capture_retry(event: RetryEvent) -> None:
    print(event.name, event.attempt_number, event.delay)

policy = RetryPolicy().attempts(3).on_retry(capture_retry)
```

For critical hooks, keep the default propagation behavior. For metrics,
tracing, or debugging observers, opt in to isolation:

```python
policy = RetryPolicy().on_event(
    "before_sleep",
    capture_retry,
    failure_mode="isolate",
)
```

Isolated failures do not include exception messages in the default report,
which helps avoid leaking tokens, URLs, or payload fragments from observer
errors.

## Event names

| Friendly method | Event name | When it runs |
|---|---|---|
| `on_before_attempt()` | `before_attempt` | Before each attempt |
| `on_success()` | `after_success` | After an accepted success |
| `on_failure()` | `after_failure` | After a failed attempt |
| `on_retry()` | `before_sleep` | Before sleeping for another attempt |
| `on_giveup()` | `after_giveup` | When Relinker gives up |

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
