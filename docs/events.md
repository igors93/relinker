# Events

Events let you connect RetryFlow to logs, metrics, tracing, or debugging tools.

```python
from retryflow import RetryPolicy
from retryflow.event import RetryEvent

def log_event(event: RetryEvent) -> None:
    print(event.name, event.attempt_number)

policy = RetryPolicy().on_event("after_failure", log_event)
```

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
