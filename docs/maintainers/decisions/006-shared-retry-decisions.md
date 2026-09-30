# 006 — Shared deterministic retry decisions

## Context

ADR 003 centralized bookkeeping in `RetryRuntime` but kept each execution
shape's control flow explicit. In practice the sync executor, the async
executor, and the sync and async retry-block context managers each carried a
full copy of the same post-attempt state machine: record the attempt, decide
retry or stop, plan the wait, reserve retry-budget capacity, emit
`before_sleep`, recheck the time budget, and give up. The give-up block alone
was repeated about a dozen times.

Every fix to that sequence had to be applied four times. A retry-budget
reservation leak, for example, could only be fixed consistently by editing all
four copies.

## Decision

`internal/executor_flow.py` provides `RetryFlow`, which owns the deterministic,
I/O-free part of one execution:

- `next_attempt()` and `enter_attempt()` start an attempt and emit
  `before_attempt`;
- `after_exception(error)` and `after_value(value, has_value=...)` record the
  attempt, emit events, and return either a `RetryWaitPlan` (sleep, then try
  again) or a `FinalDecision` (`accept`, `reject`, or `exhaust`).

Each execution shape keeps its own explicit loop. It calls the user function,
awaits it when needed, performs the sleep (releasing the reservation if the
sleep fails), and turns a `FinalDecision` into its own outcome: a return
value or exception for executors, and suppress-or-propagate for context
managers.

Runtime modules read time through `relinker.internal.clock.now()`, which is
the single patch point for fake clocks in tests.

## Consequences

The retry state machine exists once, so behavior stays aligned across `run()`,
`run_async()`, the decorator, and retry blocks by construction. Executors are
short enough to read in full. State snapshots are built only when a handler
observes the event.

Awaiting and sleeping still differ between sync and async code, and that
difference remains visible in each loop, as the architecture guide requires.

## Alternatives considered

- Keep four copies and rely on parity tests to catch drift.
- Build one universal executor parameterized by sync or async callbacks,
  which ADR 003 rejected because it hides where awaiting changes control flow.
- Generate the async code from the sync code.
