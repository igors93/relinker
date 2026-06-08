# Feature Map

A quick reference from need to API. All names listed here are stable exports.

## Core execution

| Need | API |
|---|---|
| Simple decorator | `@retry(attempts=n, delay=d, on=(Error,))` |
| Reusable policy | `RetryPolicy()` |
| Run a function | `policy.run(fn)` or `policy.run(fn, arg1, arg2)` |
| Run an async function | `policy.run_async(fn)` or `await policy.run_async(fn)` |
| Decorate a function | `@policy` |

## Stop strategies

| Need | API |
|---|---|
| Limit total attempts | `.attempts(n)` |
| Limit by elapsed time | `.max_time(seconds)` |
| Retry indefinitely | `.forever()` |
| Custom stop condition | `.stop_when(callback)` |
| Either condition stops | `.or_stop_after_attempts(n)` / `.or_stop_after_time(s)` |
| Both conditions stop | `.and_stop_after_attempts(n)` / `.and_stop_after_time(s)` |

## Retry conditions

| Need | API |
|---|---|
| Retry on exception type | `.on(ErrorA, ErrorB)` |
| Retry on returned value | `.retry_if_result(predicate)` |
| Retry on custom logic | `.retry_if(callback)` — receives `(error, value)` |
| Add another condition (any) | `.or_on(Error)` / `.or_retry_if_result(pred)` |
| Add another condition (all) | `.any_condition(...)` / `.all_conditions(...)` |
| Signal retry from application | `raise TryAgain("reason")` |

## Delays

| Need | API |
|---|---|
| No delay | `.no_delay()` |
| Fixed delay | `.fixed_delay(seconds)` |
| Linear increase | `.linear_delay(start=0.5, step=0.5, maximum=5)` |
| Exponential backoff | `.exponential_delay(base=1, factor=2, maximum=30)` |
| Random delay | `.random_delay(minimum=0, maximum=2)` |
| Random exponential | `.random_exponential_delay(base=0.25, maximum=10)` |
| Fixed sequence | `.chain_delay([0.1, 0.5, 1, 2])` |
| Custom function | `.custom_delay(lambda attempt: attempt * 0.5)` |
| State-aware delay | `.stateful_delay(callback)` — receives `RetryState` |
| Add jitter | `.jitter(maximum=0.5)` |
| Add flat offset | `.add_delay(seconds)` |

## HTTP helpers

| Need | API |
|---|---|
| Ready-to-use HTTP policy | `http_retry_policy(attempts=5, statuses={429, 503})` |
| Retry transport failures with HTTP policy | `http_retry_policy(transport_exceptions=DEFAULT_RETRYABLE_TRANSPORT_EXCEPTIONS)` |
| Retry by status code | `.retry_if_result(retry_if_status({429, 500, 503}))` |
| Respect `Retry-After` header | `.stateful_delay(retry_after_delay(default=1.0, maximum=60.0))` |
| Parse `Retry-After` manually | `parse_retry_after(header_value, default=1.0)` |
| Check one status code | `should_retry_http_status(code)` |
| Default retryable statuses | `DEFAULT_RETRYABLE_STATUSES` |
| Default transport exception set | `DEFAULT_RETRYABLE_TRANSPORT_EXCEPTIONS` |
| Maximum cap for Retry-After | `MAX_RETRY_AFTER_SECONDS` |

## Exhaustion behavior

| Need | API |
|---|---|
| Re-raise original exception (default) | `.raise_last()` |
| Return safe default value | `.fallback_value(value)` |
| Compute fallback from result | `.fallback(lambda result: ...)` |
| Raise custom exception | `.on_exhausted_raise(MyError)` |
| Return structured result | `.return_result()` |
| Raise on result exhaustion | `.raise_on_result_exhausted()` |
| Return last value on result exhaustion | `.return_last_on_result_exhausted()` |

## Shared retry capacity

| Need | API |
|---|---|
| Create shared budget | `RetryBudget(max_retries=20, per=60)` |
| Attach budget to policy | `.with_retry_budget(budget, key="service-name")` |
| Remove budget from policy | `.without_retry_budget()` |
| Inspect current capacity | `budget.snapshot(key)` |

## Results and history

| Need | API |
|---|---|
| Structured result object | `.return_result()` — returns `RetryResult` |
| Enable history recording | `.keep_history()` |
| Attempt count | `result.attempt_count` |
| Success/failure flag | `result.succeeded` / `result.failed` |
| Total elapsed time | `result.total_time` |
| Error types seen | `result.error_types` |
| Human-readable narrative | `result.story()` |
| JSON output | `result.to_json()` |

## Per-function statistics

| Need | API |
|---|---|
| Accumulated counters | `decorated_fn.retry_stats` |
| Immutable snapshot | `decorated_fn.retry_stats.snapshot()` |
| Success rate | `snapshot.success_rate` |
| Average attempts | `snapshot.average_attempts` |
| Reset counters | `decorated_fn.retry_stats.reset()` |

## Observability

| Need | API |
|---|---|
| Standard library logging | `.with_logging(level=logging.WARNING)` |
| Structured JSON logging | `.with_structured_logging()` |
| Print all events | `.debug()` |
| Hook before each attempt | `.on_before_attempt(handler)` |
| Hook on success | `.on_success(handler)` |
| Hook on failure | `.on_failure(handler)` |
| Hook before sleep | `.on_retry(handler)` |
| Hook when giving up | `.on_giveup(handler)` |
| Generic event hook | `.on_event(handler)` |
| Name a policy | `.named("payments-api")` |

## Diagnostics and guidance

| Need | API |
|---|---|
| Check for known risks | `policy.warnings()` |
| Full health report | `policy.doctor()` |
| Plain-language description | `policy.explain()` |
| Simulate timing | `policy.simulate(attempts=5)` |
| Readable timeline | `policy.timeline(attempts=5)` |
| Estimate timing (short) | `policy.preview(attempts=5)` |
| Estimate concurrent load | `policy.estimate_load(concurrent_executions=1000)` |
| Structured configuration view | `policy.to_dict()` |

## Context managers

| Need | API |
|---|---|
| Retry a sync block | `for attempt in policy.iter(name="..."): with attempt: ...` |
| Retry an async block | `async for attempt in policy.async_iter(name="..."): async with attempt: ...` |
| Set block result | `attempt.set_result(value)` |
| Read block outcome | `iterator.result` |

## Presets

| Need | API |
|---|---|
| Quick, small retry | `fast()` |
| External API / network | `network()` |
| Database transient failure | `database()` |
| Slower, patient retry | `patient()` |
| Background workers | `background_job()` |

## Testing

| Need | API |
|---|---|
| Remove real sleep | `.for_testing()` |
| Custom sleep function | `.with_sleep(lambda seconds: None)` |
| Custom async sleep | `.with_sleep(sync_fn, async_sleep=async_fn)` |
| Capture sleep durations | `.with_sleep(sleeps.append)` |

---

For method signatures and behavioral contracts, see [API reference](api.md).

For full behavioral details, see [Retry lifecycle](../concepts/retry-lifecycle.md)
and [Exhaustion behavior](../concepts/exhaustion.md).
