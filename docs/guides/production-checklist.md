# Production Checklist

Use this checklist before deploying retry behavior to a production environment.

Run these three commands on every new policy:

```python
print(policy.explain())            # plain-language description
print(policy.preview(attempts=5))  # estimated timing
print(policy.doctor().describe())  # known risks
```

If `risk_level` is `risky`, review the policy before proceeding.

---

## Policy behavior

- [ ] **Does the policy have a clear stop condition?**

  A policy without `.attempts()` or `.max_time()` allows only one attempt by
  default. Add a stop condition appropriate for the operation.

- [ ] **Is `forever()` truly required?**

  `forever()` is valid for long-running background workers, but it requires
  delays, cancellation support, monitoring, and alerting. Without these, a
  persistent failure can block indefinitely.

- [ ] **Is there a delay between attempts?**

  A policy with no delay retries as fast as the CPU allows. This can exhaust
  resources and overwhelm a recovering service. Use at minimum a fixed delay.

- [ ] **Is jitter needed to avoid retry storms?**

  When many clients fail together and retry at fixed intervals, they fire again
  simultaneously. Add `.jitter(maximum=0.5)` to spread them out.

- [ ] **Are exception types specific enough?**

  `.on(Exception)` retries every failure including bugs and validation errors.
  Name the specific exceptions that can resolve on their own.

- [ ] **Does result-based retry have clear exhaustion behavior?**

  With `retry_if_result`, if retries run out and no exhaustion behavior is
  configured, the last value is returned silently. Add `.return_result()`,
  `.raise_on_result_exhausted()`, or `.fallback()` to make it explicit.

- [ ] **Is fallback behavior intentional?**

  A fallback value should be distinguishable from a real result. Silent
  degradation can hide outages. Consider logging or emitting an event when a
  fallback is used.

- [ ] **Is the total possible sleep acceptable?**

  Use `policy.simulate(attempts=n).total_sleep` to estimate maximum wait.
  A `high_total_sleep` warning fires when the simulated total exceeds 300s.

---

## External services

- [ ] **Could retries increase pressure on a degraded service?**

  Retrying during an outage adds load exactly when the service is least able to
  handle it. Use `RetryBudget` when many executions share the same service.

- [ ] **Is the operation safe to repeat?**

  Non-idempotent operations (payments, order creation, email sending) must have
  application-level safeguards before automated retry is safe. See
  [When not to retry](when-not-to-retry.md).

- [ ] **Are non-idempotent HTTP methods reviewed carefully?**

  `POST` and `PATCH` requests may cause duplicate side effects if the server
  receives the same request twice.

- [ ] **Does the API provide `Retry-After`?**

  Rate-limited APIs often send a `Retry-After` header. Use
  `retry_after_delay(default=1.0, maximum=60.0)` to respect it automatically.

- [ ] **Should the policy use `RetryBudget`?**

  When 100 or more concurrent executions target the same service, a shared
  budget limits total retry rate. Estimate load with
  `policy.estimate_load(concurrent_executions=n)`.

---

## Observability

- [ ] **Are retries logged or observable?**

  Use `.with_logging()`, `.on_retry()`, or `.return_result()` so that retries
  are visible in logs or metrics. Silent retries make incidents harder to
  diagnose.

- [ ] **Is structured logging safe by default?**

  `.with_structured_logging()` excludes exception messages by default because
  they can contain tokens, URLs, or user data. Enable
  `include_error_message=True` only when the environment is safe.

- [ ] **Are sensitive error messages excluded from logs?**

  Exception messages from external services can contain API keys, user
  identifiers, or PII. Do not log them to shared or uncontrolled destinations.

- [ ] **Is retry history bounded?**

  The default retains at most 1000 attempt records. Review `keep_history(None)`
  carefully for workers and effectively infinite retry loops, because retained
  exception objects can make memory usage grow without bound.

- [ ] **Are retry metrics needed?**

  Consider emitting counters on `on_retry` and `on_giveup` events. Per-function
  statistics are available via `decorated_fn.retry_stats`.

- [ ] **Does the team know how to inspect `RetryResult`?**

  `return_result()` gives access to `attempt_count`, `total_time`, `history`,
  and `story()`. Share this with the team before an incident occurs.

---

## Testing

- [ ] **Are tests avoiding real sleep?**

  Use `.for_testing()` or `.with_sleep(lambda s: None)` to replace sleep with
  a no-op. Tests should run in milliseconds.

- [ ] **Are exhausted paths tested?**

  Verify that exhaustion behaves correctly: the right exception is raised, or
  the fallback value is returned, or `result.exhausted` is `True`.

- [ ] **Are fallback paths tested?**

  Test that the fallback value is valid and distinguishable from a real result.

- [ ] **Are async retry paths tested if used?**

  Async functions need async test paths. Use `policy.run_async()` and
  `await policy.run_async()` in async test functions.

---

## Related pages

- [Choosing a policy](choosing-a-policy.md)
- [Common mistakes](common-mistakes.md)
- [When not to retry](when-not-to-retry.md)
- [Safety](safety.md)
- [Diagnostics](diagnostics.md)
