# Common patterns

## Network call

Retry a flaky external API with exponential backoff and jitter:

```python
from relinker import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(5)
    .on(ConnectionError, TimeoutError, OSError)
    .exponential_delay(base=0.5, factor=2, maximum=10)
    .jitter(maximum=0.5)
)

@policy
def fetch_data(url: str) -> dict:
    return http_client.get(url)
```

## Database-like operation

Short retry with bounded delay for transient database errors:

```python
from relinker import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(4)
    .on(TimeoutError, ConnectionError)
    .exponential_delay(base=0.1, factor=2, maximum=2)
    .jitter(maximum=0.2)
)

@policy
def load_user(user_id: int) -> dict:
    return db.query("SELECT * FROM users WHERE id = ?", user_id)
```

## Polling

Poll until a resource reaches the desired state:

```python
from relinker import RetryPolicy, TryAgain

policy = RetryPolicy().attempts(20).fixed_delay(1)

def wait_for_job(job_id: str) -> str:
    status = job_service.get_status(job_id)
    if status == "pending":
        raise TryAgain(f"job {job_id} is still pending")
    return status

result = policy.run(wait_for_job, "job-123")
```

Or use `retry_if_result`:

```python
policy = (
    RetryPolicy()
    .attempts(20)
    .retry_if_result(lambda status: status != "completed")
    .fixed_delay(1)
    .return_result()
)

result = policy.run(lambda: job_service.get_status("job-123"))
```

## Fallback

Return a safe default value when all retries are exhausted:

```python
from relinker import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(3)
    .on(ConnectionError)
    .fixed_delay(0.5)
    .fallback(lambda result: {"items": [], "cached": True})
)

data = policy.run(fetch_catalogue)
```

## Diagnostics

Check a policy for known risk patterns before deployment:

```python
policy = RetryPolicy().forever().on(Exception).no_delay()

for warning in policy.warnings():
    print(f"[{warning.code}] {warning.message}")
    if warning.hint:
        print(f"  Hint: {warning.hint}")

# Simulate delays
print(policy.simulate(attempts=5).describe())
```

## Statistics

Track per-function retry counts for monitoring:

```python
from relinker import RetryPolicy

@RetryPolicy().attempts(5).on(TimeoutError)
def call_api():
    return fetch()

# After some calls:
snap = call_api.retry_stats.snapshot()
print(f"Success rate: {snap.success_rate:.1%}")
print(f"Average attempts: {snap.average_attempts:.1f}")
print(snap.to_dict())
```

## Async call

Async functions work the same as sync functions:

```python
import asyncio
from relinker import RetryPolicy

policy = RetryPolicy().attempts(3).on(ConnectionError).exponential_delay(base=0.5)

@policy
async def fetch_async(url: str) -> dict:
    return await async_client.get(url)

result = asyncio.run(fetch_async("https://api.example.com/data"))
```

## Logging integration

Add standard library logging to any policy:

```python
import logging
from relinker import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError)
    .exponential_delay(base=0.5)
    .with_logging(level=logging.WARNING)
)
```

## Result inspection

Inspect what happened after retry exhaustion:

```python
result = policy.return_result().run(task)

print(result.summary())
print(f"Attempts: {result.attempt_count}")
print(f"Failed attempts: {result.failed_attempts}")
print(f"Error types seen: {[t.__name__ for t in result.error_types]}")
print(result.to_json(indent=2))
```

## State-aware delay

Adapt delay based on execution state:

```python
from relinker import RetryPolicy, RetryState

def backoff_by_error_type(state: RetryState) -> float:
    if isinstance(state.last_error, TimeoutError):
        return 5.0  # longer wait for timeouts
    return 1.0

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError, ConnectionError)
    .stateful_delay(backoff_by_error_type)
)
```

## HTTP Retry-After

Honour the server's requested delay using state-aware retry:

```python
from relinker import RetryPolicy
from relinker.http import retry_if_status, retry_after_delay

RETRYABLE = {429, 500, 502, 503, 504}

policy = (
    RetryPolicy()
    .attempts(5)
    .retry_if_result(retry_if_status(RETRYABLE))
    .stateful_delay(retry_after_delay(default=1.0, maximum=60.0))
    .return_result()
)

result = policy.run(lambda: my_http_client.get("/api/data"))
```
