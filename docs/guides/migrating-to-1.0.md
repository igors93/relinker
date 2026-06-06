# Migrating to Relinker 1.0

## Who should read this

This guide is for users upgrading from Relinker `0.8.x` or any earlier version.

## Compatibility summary

There are no intentional breaking changes to the public documented API of
`0.8.0`. Version `1.0.0` formalizes the contracts that were already protected
by the test suite:

- Imports from internal modules were never guaranteed. Users who relied on
  undocumented paths should migrate to the stable imports below.
- Users should import from the root package or from documented modules.

## Stable imports

The stable root imports are:

```python
from relinker import RetryBudget, RetryPolicy, RetryResult, retry
```

The documented module exports of `relinker.context` are:

```python
from relinker.context import (
    AsyncRetryAttemptContext,
    AsyncRetryBlockIterator,
    RetryAttemptContext,
    RetryBlockIterator,
)
```

The following are internal and carry no compatibility guarantee:

- `relinker.internal` — implementation details that may change without notice.
- `relinker.context._shared` — shared internal helpers, not part of the public
  module API.
- Any underscore-prefixed object, even when it appears near public code.

## Exhaustion behavior

When all retry attempts are exhausted, Relinker applies the last exhaustion
configuration that was set on the policy. Configurations are mutually exclusive
and contradictory combinations are rejected at configuration time.

Last-configuration-wins means:

```python
# raise_last wins — the fallback is discarded
RetryPolicy().fallback_value("safe").raise_last()

# fallback wins — raise_last is discarded
RetryPolicy().raise_last().fallback_value("safe")
```

The following exhaustion modes are supported:

- `raise_last()` — re-raises the last exception from the final attempt.
- `return_result()` — returns the full `RetryResult` object instead of
  raising or unwrapping.
- `fallback_value(v)` / `fallback(fn)` — returns a fixed value or calls a
  function when exhausted.
- `on_exhausted_raise(exc_type)` — raises a custom exception type.

## None results

Relinker distinguishes two distinct outcomes:

- A function returned `None` explicitly. This is a successful result. The run
  succeeded and `RetryResult.has_last_value` is `True`.
- A context-manager block completed without calling `set_result()`. This
  indicates no result was set. `RetryResult.has_last_value` is `False`.

Do not treat `None` as a sentinel for "no result" in application code. Use
`RetryResult.has_last_value` or `RetryResult.succeeded` to distinguish these
cases.

## Context-manager imports

`relinker.context` became a package internally in an earlier release. The
public imports documented above were preserved across that change and remain
stable. No migration is required if you imported from `relinker` or
`relinker.context` using the documented names.

## Retry Budget

`RetryBudget` is process-local and in-memory:

- Multiple executions share capacity only when they use **the same instance**
  with **the same key**.
- The original call never consumes capacity — only additional retry attempts do.
- Relinker does not provide a distributed rate limiter or cross-process retry
  coordination. See [Retry budgets](../concepts/retry-budgets.md) for the
  complete scope.
- Normal policy delays and `max_time()` continue to apply alongside budget
  waiting.

## Python support

Relinker 1.0.0 officially supports:

- Python 3.10
- Python 3.11
- Python 3.12
- Python 3.13

## Deprecation policy

From `1.0.0`, the deprecation policy documented in
[`docs/reference/compatibility.md`](../reference/compatibility.md) applies.
Public APIs are deprecated in a minor release and removed only in a later major
release.

## Checklist

- [ ] Replace imports from undocumented internal modules.
- [ ] Run the application test suite against `1.0.0`.
- [ ] Review exhaustion configuration order.
- [ ] Verify async cancellation and shutdown behavior.
- [ ] Confirm Retry Budget scope matches the deployment model.
