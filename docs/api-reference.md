# API Reference

This is a practical overview of the public API.

## Main imports

```python
from retryflow import RetryPolicy, retry, TryAgain
from retryflow import fast, network, database, patient, background_job
from retryflow import RetryWrappedFunction
```

## RetryPolicy

### Stop methods

```python
RetryPolicy().attempts(3)
RetryPolicy().max_time(30)
RetryPolicy().forever()
RetryPolicy().or_stop_after_time(30)
RetryPolicy().or_stop_after_attempts(5)
```

### Retry conditions

```python
RetryPolicy().on(TimeoutError, ConnectionError)
RetryPolicy().retry_if_result(lambda value: value is None)
RetryPolicy().retry_if(lambda error, value: True)
RetryPolicy().or_on(OSError)
RetryPolicy().or_retry_if_result(lambda value: value == "retry")
```

### Delay methods

```python
RetryPolicy().no_delay()
RetryPolicy().fixed_delay(1)
RetryPolicy().linear_delay(start=1, step=2, maximum=10)
RetryPolicy().chain_delay([0.1, 0.5, 1, 2])
RetryPolicy().exponential_delay(base=1, maximum=30)
RetryPolicy().random_delay(minimum=0, maximum=1)
RetryPolicy().random_exponential_delay(base=1, maximum=30)
RetryPolicy().jitter(maximum=0.5)
RetryPolicy().custom_delay(lambda attempt: attempt * 0.5)
```

### Exhausted behavior

```python
RetryPolicy().return_result()
RetryPolicy().fallback_value(None)
RetryPolicy().fallback(lambda result: None)
RetryPolicy().on_exhausted_raise(RuntimeError)
RetryPolicy().raise_on_result_exhausted()
```

### Observability

```python
RetryPolicy().debug()
RetryPolicy().with_logging()
RetryPolicy().with_logging(level=logging.INFO)
RetryPolicy().with_logging(logger=my_logger)
RetryPolicy().on_event("before_sleep", handler)
```

### Diagnostics

```python
RetryPolicy().warnings()
RetryPolicy().simulate(attempts=5)
RetryPolicy().timeline(attempts=5)
RetryPolicy().explain()
```

### Execution

```python
policy.run(function, *args, **kwargs)
await policy.run_async(function, *args, **kwargs)
```

### Decorator

```python
@RetryPolicy().attempts(3)
def task() -> str:
    return "ok"
```

Decorated functions receive:

```python
task.retry_stats        # RetryStats instance
task.retry_policy       # the policy used
task.with_policy(p)     # re-decorate with a different policy
```

The `RetryWrappedFunction` Protocol describes these attributes for type checking:

```python
from retryflow import RetryWrappedFunction

def expect_wrapped(fn: RetryWrappedFunction) -> None:
    snap = fn.retry_stats.snapshot()
    print(snap.calls)
```

## TryAgain

Raise `TryAgain` from inside a wrapped function to request another attempt, regardless of the configured retry condition:

```python
from retryflow import TryAgain

def task():
    result = call_service()
    if result == "pending":
        raise TryAgain("not ready yet")
    return result
```

See [TryAgain](try-again.md) for full documentation.

## retry decorator

```python
@retry
def task() -> str:
    return "ok"

@retry(attempts=5, delay=1, on=(TimeoutError,))
def call_api() -> str:
    return "response"
```

Use `@retry` for simple cases. Use `RetryPolicy` or presets for advanced behavior.

## RetryResult

Properties and methods on the result object:

```python
result.succeeded
result.failed
result.exhausted
result.attempt_count
result.total_time
result.error
result.value
result.retry_cause
result.exhausted_by_exception
result.exhausted_by_result
result.last_error         # error from most recent failed attempt
result.last_value         # value from most recent successful attempt
result.failed_attempts    # count of failed attempts
result.successful_attempts  # count of successful attempts
result.error_types        # tuple of distinct exception types seen

result.last_attempt()
result.summary()          # compact dict for logging
result.to_dict()
result.to_json(indent=2)
result.story()
```

## RetrySimulation

Properties and methods on a simulation object:

```python
sim = policy.simulate(attempts=5)

sim.attempt_count
sim.total_sleep
sim.max_delay
sim.stops_early
sim.attempts    # tuple of RetrySimulationAttempt

sim.to_dict()
sim.to_json(indent=2)
sim.describe()
```

Each `RetrySimulationAttempt`:

```python
attempt.attempt_number
attempt.delay_before_next_attempt
attempt.cumulative_sleep
attempt.stops_after_attempt
```

## HTTP helpers

```python
from retryflow.http import (
    should_retry_http_status,
    retry_if_status,
    retry_after_delay,
    parse_retry_after,
)
```

See [HTTP helpers](http.md) for full documentation.
