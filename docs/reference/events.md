# Events

Events let you connect Relinker to logs, metrics, tracing, or debugging tools.

```python
from relinker import RetryPolicy
from relinker.event import RetryEvent

def log_event(event: RetryEvent) -> None:
    print(event.name, event.attempt_number)

policy = RetryPolicy().on_event("after_failure", log_event)
```

By default, handler failures propagate and stop the retry flow. For
observational hooks such as metrics, use isolation:

```python
policy = RetryPolicy().on_event(
    "before_sleep",
    publish_metric,
    failure_mode="isolate",
)
```

Isolated handlers catch only `Exception`, report the failure through the
`relinker.events` logger without the exception message, and continue to later
handlers. `KeyboardInterrupt`, `SystemExit`, and cancellation-style
`BaseException` subclasses are never isolated.

Each event can include a `RetryState` object:

```python
def log_event(event: RetryEvent) -> None:
    if event.state is not None:
        print(event.state.elapsed)
        print(event.state.will_retry)
```

Event names:

- `before_attempt`
- `after_success`
- `after_failure`
- `before_sleep`
- `after_giveup`
