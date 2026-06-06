# Retry lifecycle

A Relinker execution follows a small, predictable cycle. Understanding this
cycle helps when reviewing policies, interpreting events, and changing internal
implementation without changing public behavior.

## 1. Start the execution

Relinker creates runtime state and begins attempt `1`. The first attempt is the
original call, not a retry. A configured `RetryBudget` therefore does not consume
capacity before the original call.

Before calling user code, Relinker emits `before_attempt`.

## 2. Record the outcome

An attempt ends in one of two ways:

- it raises an exception;
- it returns a value, including `None`.

Returned `None` is still a real value. `RetryState.has_value` and
`RetryResult.has_last_value` distinguish it from an attempt that produced no
value because it raised.

## 3. Decide whether the outcome should retry

For an exception, the configured retry condition is evaluated. `TryAgain` is an
explicit retry signal and bypasses the normal exception filter. Exceptions
outside the configured condition are propagated immediately.

For a returned value, result predicates decide whether the value is accepted or
should be retried. A rejected result is not an exception and does not emit
`after_failure`.

## 4. Decide whether another attempt is allowed

If the outcome requests a retry, the stop strategy checks the current attempt
number and elapsed time. Examples include:

- `attempts(n)` for a maximum number of calls;
- `max_time(seconds)` for a retry-loop time budget;
- composed stop strategies.

`max_time()` is not a hard timeout for user code already running. It is checked
between attempts and before sleeping.

## 5. Plan one wait

Relinker resolves the configured delay strategy. When a `RetryBudget` is active,
it also reserves shared capacity. The final wait is represented as:

- `policy_delay`: delay from backoff, jitter, `Retry-After`, or a custom strategy;
- `budget_delay`: additional wait required by shared retry capacity;
- `next_delay`: the actual total wait.

The budget never shortens the policy delay. Relinker performs one sleep for the
total wait.

If `max_time()` rejects the planned wait, or if sleep is interrupted or canceled,
the unused retry-budget reservation is released.

## 6. Emit observable events

A failure followed by a successful retry has this event order:

```text
before_attempt
after_failure
before_sleep
before_attempt
after_success
```

When attempts are exhausted by an exception:

```text
before_attempt
after_failure
after_giveup
```

Result-based retries omit `after_failure` because no exception occurred.

## 7. Finish the execution

When no retry is needed, the accepted value is returned. When another retry is
not allowed, the configured exhaustion behavior is applied: re-raise, fallback,
custom exception, last rejected result, or `RetryResult`.

See [Exhaustion behavior](exhaustion.md) for the complete precedence rule.

## Execution paths

The same public semantics apply to:

- `RetryPolicy.run()`;
- `RetryPolicy.run_async()`;
- synchronous and asynchronous decorated functions;
- synchronous and asynchronous retry-block context managers.

Contract tests in `tests/contracts/` protect parity between these paths.
