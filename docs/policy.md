# Policy

`RetryPolicy` is the main configuration object in RetryFlow.

A policy is immutable. Every configuration method returns a new policy.

```python
from retryflow import RetryPolicy

base = RetryPolicy()
api = base.attempts(5).on(TimeoutError)
```

## Stop strategies

```python
RetryPolicy().attempts(3)
RetryPolicy().max_time(10)
RetryPolicy().forever()
```

You can combine stop strategies:

```python
policy = RetryPolicy().attempts(5).or_stop_after_time(30)
```

## Delay strategies

```python
RetryPolicy().fixed_delay(1)
RetryPolicy().exponential_delay(base=1, maximum=30)
RetryPolicy().random_delay(minimum=0, maximum=2)
```

Add jitter to the current delay:

```python
policy = RetryPolicy().exponential_delay(base=1).jitter(maximum=0.5)
```

## Conditions

```python
RetryPolicy().on(TimeoutError, ConnectionError)
RetryPolicy().retry_if_result(lambda value: value is None)
```

Combine conditions:

```python
from retryflow.conditions.exception import ExceptionCondition
from retryflow.conditions.result import ResultCondition

condition = ExceptionCondition((TimeoutError,)) | ResultCondition(lambda value: value is None)
policy = RetryPolicy(condition=condition)
```
