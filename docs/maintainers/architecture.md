# Architecture

Relinker is organized around one goal: keep the public retry policy readable
while isolating execution details behind small components.

## Package map

```text
src/relinker/
├── policy.py          public immutable policy builder
├── retry.py           simple decorator entry point
├── budget.py          process-local shared retry capacity
├── context.py         sync and async retry-block interfaces
├── result.py          final execution result
├── state.py           immutable runtime state snapshots
├── attempt.py         one recorded attempt
├── event.py           observable lifecycle events
├── stats.py           per-decorated-function statistics
├── http.py            dependency-free HTTP helpers
├── presets.py         ready-to-customize policies
├── conditions/        retry decisions
├── delays/            wait strategies
├── stop/              stop strategies
├── executors/         sync and async execution loops
└── internal/          shared implementation details
```

## Responsibility boundaries

### `RetryPolicy`

`RetryPolicy` stores configuration and provides the fluent public API. It should
not own a retry loop. Builder methods return new policies rather than mutating an
existing instance.

### Conditions

Conditions answer only whether an exception or returned value should retry. They
do not sleep, emit events, or decide exhaustion behavior.

### Stop strategies

Stop strategies answer whether another attempt is allowed from attempt count and
elapsed time. They do not inspect application exceptions or returned values.

### Delay strategies

Delay strategies compute policy wait time. They do not perform sleep. Stateful
delays receive a `RetryState` snapshot instead of executor internals.

### Retry Budget

`RetryBudget` reserves retry capacity by object and key. It is thread-safe,
process-local, and independent from sleep. `internal/retry_wait.py` combines its
reservation with the normal policy delay.

### Executors and context managers

Executors coordinate user calls, records, conditions, stop strategies, waits,
events, and final behavior. Sync and async loops remain separate where awaiting
changes control flow. Shared deterministic operations may be extracted, but a
single highly-parameterized universal executor should be avoided.

`relinker.context` is a package that preserves the public import surface while
separating synchronous and asynchronous control flow into `sync.py` and
`async_.py`. `_shared.py` contains only common state and identical helper
behavior.

`internal/runtime.py` centralizes mutable attempt history, aggregate counters,
`RetryState` construction, and `RetryResult` construction shared by executors
and context managers. RetryRuntime remains responsible for attempt history,
counters, `RetryState`, and `RetryResult` construction.

### Results and state

`AttemptRecord`, `RetryState`, and `RetryResult` are immutable observable data.
Aggregate counters must describe the full execution even when retained history
is bounded.

## Dependency direction

Preferred direction:

```text
public facade
    -> strategies and models
    -> executors/context coordination
    -> internal deterministic helpers
```

Internal helpers may depend on public models. Public strategy modules should not
depend on concrete executors.

## Invariants

Changes must preserve these invariants:

1. the original call is attempt `1`;
2. only additional attempts consume Retry Budget capacity;
3. a returned `None` remains distinguishable from no returned value;
4. the final exhaustion configuration called by the user wins;
5. interrupted or canceled waits preserve the original interruption;
6. unused Retry Budget reservations are released;
7. sync, async, decorator, and context-manager paths remain behaviorally aligned;
8. internal refactoring does not change the public import surface accidentally.

## Safe refactoring process

1. Add or confirm a contract test for the behavior being touched.
2. Make one focused internal change.
3. Run contract tests and the full suite.
4. Run Ruff, mypy, package build, and metadata validation.
5. Keep documentation and changelog changes in a reviewable commit.

Do not replace whole core files from an older snapshot. Apply minimal changes to
the current branch so fixes and contracts already present are preserved.

## Extension guidance

Add a new strategy when the behavior is independently testable and composes with
the existing protocols. Add a new internal abstraction only when it removes real,
repeated logic without hiding the retry lifecycle.

Prefer a few explicit lines in sync and async executors over a generic abstraction
that makes control flow difficult to follow.
