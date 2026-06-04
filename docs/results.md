# Results

`RetryResult` is the full execution record returned when you use `.return_result()`.

## Getting a result

```python
result = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError)
    .return_result()
    .run(task)
)
```

Or via a decorated function:

```python
@RetryPolicy().attempts(5).on(TimeoutError).return_result()
def task() -> str:
    return fetch()
```

## Core fields

| Property | Type | Description |
|----------|------|-------------|
| `succeeded` | `bool` | True when execution ended with an accepted value |
| `failed` | `bool` | True when execution ended with an error or exhausted |
| `exhausted` | `bool` | True when the stop strategy fired |
| `retry_cause` | `"exception" \| "result" \| None` | What caused the retry |
| `attempt_count` | `int` | Total number of attempts made |
| `total_time` | `float` | Total execution time in seconds |
| `value` | `T \| None` | Final returned value (when succeeded) |
| `error` | `BaseException \| None` | Final exception (when failed by exception) |

## New properties

### last_error

Returns the exception from the most recent failed attempt, regardless of whether
the overall execution eventually succeeded:

```python
result = policy.return_result().run(task)

if result.last_error is not None:
    print(f"Last error was: {type(result.last_error).__name__}")
```

### last_value

Returns the value from the most recent attempt that returned a value (even if
that value was rejected by a result condition):

```python
result = policy.return_result().run(task)
print(result.last_value)
```

### failed_attempts / successful_attempts

Count individual attempts by outcome:

```python
result = policy.return_result().run(task)
print(f"Failed: {result.failed_attempts}, Succeeded: {result.successful_attempts}")
```

### error_types

Returns the distinct exception types raised across all attempts, in order of
first occurrence:

```python
result = policy.return_result().run(task)
names = [t.__name__ for t in result.error_types]
print(names)  # e.g. ["TimeoutError", "ConnectionError"]
```

## summary()

Returns a compact dict suitable for structured logging. Values are excluded by
default to avoid leaking sensitive data:

```python
import json
result = policy.return_result().run(task)
print(json.dumps(result.summary()))
```

Example output:

```json
{
  "succeeded": false,
  "exhausted": true,
  "retry_cause": "exception",
  "attempt_count": 5,
  "failed_attempts": 5,
  "total_time": 1.234,
  "error": "TimeoutError",
  "error_types": ["TimeoutError"]
}
```

## to_dict()

Returns a detailed JSON-friendly dict. By default, the returned value is not
included:

```python
d = result.to_dict()
d_with_value = result.to_dict(include_value=True)
```

## to_json()

Serializes the result as JSON:

```python
print(result.to_json(indent=2))
```

If `include_value=True` and the value is not JSON-serializable, `json.dumps`
will raise. This is intentional.

## story()

Returns a human-readable execution narrative:

```python
print(result.story())
```

Example output:

```
RetryFlow execution story

Status: exhausted by exception
Attempts: 3
Total time: 0.3210s

Attempt 1: failed in 0.0850s
  Error: TimeoutError: connection timed out
Attempt 2: failed in 0.0920s
  Error: TimeoutError: connection timed out
Attempt 3: failed in 0.1440s
  Error: TimeoutError: connection timed out
```

## Exhaustion types

| Field | Meaning |
|-------|---------|
| `exhausted_by_exception` | Retry stopped after repeated exceptions |
| `exhausted_by_result` | Retry stopped after repeated rejected return values |

```python
if result.exhausted_by_exception:
    print("All retries failed with exceptions")
elif result.exhausted_by_result:
    print("Result was never accepted")
```

## Attempt records

Each `AttemptRecord` in `result.attempts` contains:

| Field | Description |
|-------|-------------|
| `number` | One-based attempt number |
| `started_at` | Monotonic timestamp (start) |
| `ended_at` | Monotonic timestamp (end) |
| `duration` | Duration in seconds |
| `value` | Returned value (if no exception) |
| `error` | Raised exception (if failed) |
| `succeeded` | True when no exception was raised |
| `failed` | True when an exception was raised |
