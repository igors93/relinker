# Diagnostics

Diagnostics help users understand retry behavior before production.

RetryFlow does not block risky application-level decisions. Instead, it gives
advisory tools.

## Warnings

```python
from retryflow import RetryPolicy

policy = RetryPolicy().forever().on(Exception).no_delay()

for warning in policy.warnings():
    print(warning.code)
    print(warning.message)
    print(warning.hint)
```

Warnings are non-blocking. They are useful in tests, reviews, CLI tools, or
startup checks.

Possible warnings include:

- retry forever
- no delay
- retrying all `Exception` subclasses
- `return_result()` precedence over fallback behavior

## Simulation

```python
policy = RetryPolicy().exponential_delay(base=1, maximum=30)

simulation = policy.simulate(attempts=5)

print(simulation.total_sleep)
print(simulation.describe())
```

Simulation does not call user code. It only estimates wait behavior.

## Timeline alias

`timeline()` is a readable alias over simulation:

```python
print(policy.timeline(attempts=5))
```

## Why diagnostics matter

Retry can make a system safer, but it can also make incidents worse if a policy
is too aggressive. Diagnostics help users understand behavior without forcing
rules on them.
