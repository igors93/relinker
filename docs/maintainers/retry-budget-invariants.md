# RetryBudget Invariants

`RetryBudget` is a process-local retry capacity guard. It is not a general
rate limiter: it only controls additional retry attempts for policies that
share the same `RetryBudget` object and key.

These invariants are maintenance contracts for implementation changes.

## B1: Rolling-window capacity

For every window ending at time `t`:

```text
count(scheduled_at in (t - per, t]) <= max_retries
```

The window is open on the left and closed on the right. Boundary changes must
preserve that exact shape.

## B2: Earliest legal slot

`_reserve()` returns the smallest representable `float` that is no earlier than
the requested `not_before` and still preserves B1. Returning merely "a later
legal slot" is not enough.

## B3: Atomic reservation

Concurrent reservations for the same key must observe already reserved capacity.
The lock protects the read, slot choice, token creation, and insertion as one
operation.

## B4: Idempotent release

Releasing a reservation removes only that reservation. Releasing the same token
again is harmless and must not affect other reservations.

## B5: Per-key independence

Different keys do not share logical capacity. They may share the same lock as an
implementation detail, but a reservation on one key must not consume capacity
from another key.

## B6: Initial calls do not consume budget

Only additional attempts reserve retry capacity. The first execution attempt is
not a retry and must not call `_reserve()`.

## B7: No unbounded ULP walk

The algorithm may inspect neighboring representable floats around a relevant
boundary, but it must not advance one ULP at a time for an unbounded distance
while holding the lock.

## B8: No external work under lock

The budget lock must not protect user code, sleeps, event handlers, logging,
delay callbacks, or other externally supplied behavior.

## B9: Snapshot consistency

`snapshot()` fields (`active`, `queued`, `available`, and `next_available_in`)
must come from the same protected view of one key's reservations.

## Test Strategy

The permanent tests include:

- boundary regressions for decimal periods and `math.nextafter()` cases;
- a small reference model that checks windows exhaustively and compares the
  first legal slot for generated schedules;
- concurrent reservation/release/snapshot tests;
- integration tests proving only retry attempts consume capacity.

`benchmarks/retry_budget.py` measures reservation, release, and snapshot costs
for several capacities and schedule shapes. It prints local diagnostics and
does not enforce machine-dependent timing thresholds in the regular test suite.
