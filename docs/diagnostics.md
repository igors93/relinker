# Diagnostics and Guidance

RetryFlow is built around guidance. It does not block application-level decisions, but it helps users detect surprising or risky policies.

## Warnings

```python
from retryflow import RetryPolicy

policy = RetryPolicy().forever().on(Exception).no_delay()

for warning in policy.warnings():
    print(warning.code, warning.message)
```

Warnings are advisory and non-blocking.

## Doctor

`doctor()` returns a `PolicyHealthReport`.

```python
report = policy.doctor()

print(report.risk_level)
print(report.describe())
```

Risk levels:

- `ok`: no warnings
- `warning`: something deserves review
- `risky`: the policy may cause serious operational problems

## Explain

`explain()` describes what the policy does in human language.

```python
print(policy.explain())
```

This is useful in:

- code reviews
- debugging sessions
- documentation
- production readiness checks

## Preview

`preview()` shows an estimated timeline without running user code.

```python
print(policy.preview(attempts=5))
```

## Timeline and simulation

Use `simulate()` when you want structured data:

```python
simulation = policy.simulate(attempts=5)

print(simulation.to_dict())
print(simulation.describe())
```

Use `timeline()` when you want the readable simulation report directly:

```python
print(policy.timeline(attempts=5))
```

## Common warnings

| Warning | Meaning |
|---|---|
| `forever` | The policy can retry forever |
| `no_delay` | The policy has no sleep between attempts |
| `tight_loop_risk` | The policy can retry forever without sleeping |
| `broad_exception` | The policy retries all `Exception` subclasses |
| `many_attempts` | The policy uses many attempts |
| `high_total_sleep` | The simulated sleep time is high |
| `result_retry_without_observation` | Result-based retry may exhaust silently |
| `return_result_precedence` | `return_result()` takes precedence over fallback or exhausted errors |

## Production recommendation

Before deploying a retry policy, run:

```python
print(policy.explain())
print(policy.preview(attempts=5))
print(policy.doctor().describe())
```
