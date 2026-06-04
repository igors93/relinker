# Safety

Retry is powerful, but it can make incidents worse when used without care.

RetryFlow does not force application-level rules. Instead, it gives tools that
help users reason about behavior.

## Use specific exceptions when possible

```python
RetryPolicy().on(TimeoutError, ConnectionError)
```

Avoid retrying every exception unless that is intentional:

```python
RetryPolicy().on(Exception)
```

## Prefer backoff and jitter for external services

```python
policy = (
    RetryPolicy()
    .attempts(5)
    .exponential_delay(base=1, maximum=30)
    .jitter(maximum=0.5)
)
```

This helps avoid many clients retrying at exactly the same moment.

## Be careful with retry forever

```python
RetryPolicy().forever()
```

This can be valid for background workers, but the application should control
shutdown, cancellation, monitoring, and alerting.

## Be careful with non-idempotent operations

Retrying operations like payments, order creation, or email sending can duplicate
side effects if the operation is not idempotent.

Use idempotency keys or application-level safeguards.

## Use diagnostics

```python
warnings = RetryPolicy().forever().on(Exception).no_delay().warnings()
```

Warnings are advisory and do not block your application.
