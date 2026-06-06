# Relinker Documentation

**Simple by default, powerful by composition, safe by guidance.**

Relinker's documentation is organized by task. Existing guides keep their stable
paths while newer concept, reference, and maintainer documents live in focused
subdirectories.

## Start here

| Guide | Purpose |
|---|---|
| [Getting started](getting-started.md) | Install Relinker and run a first retry policy |
| [Policy builder](policy-builder.md) | Learn the fluent, immutable `RetryPolicy` API |
| [Production checklist](production-checklist.md) | Review a policy before deploying it |

## Core concepts

| Concept | Purpose |
|---|---|
| [Retry lifecycle](concepts/retry-lifecycle.md) | Understand one execution from first call to final outcome |
| [Conditions](conditions.md) | Decide which exceptions or results should retry |
| [Stop strategies](stop.md) | Limit attempts, elapsed time, or composed stop rules |
| [Delays](delays.md) | Configure fixed, exponential, random, and custom waits |
| [Exhaustion behavior](concepts/exhaustion.md) | Choose what happens when another retry is no longer allowed |
| [Retry budgets](retry-budgets.md) | Share process-local retry capacity during incidents |
| [Results and statistics](results.md) | Inspect final outcomes and aggregate counters |
| [Runtime state](state.md) | Understand the immutable state exposed to hooks and delays |

## Usage guides

| Guide | Purpose |
|---|---|
| [Async execution](async.md) | Retry coroutine functions safely |
| [Context manager usage](context-manager.md) | Retry inline sync and async blocks |
| [HTTP retry](http.md) | Retry status codes and respect `Retry-After` |
| [Observability](observability.md) | Use logging, structured logging, and events |
| [Diagnostics and guidance](diagnostics.md) | Use warnings, doctor, preview, and explain |
| [Testing retry code](testing.md) | Keep tests deterministic and avoid real sleeping |
| [Common patterns](common-patterns.md) | Apply Relinker to recurring application scenarios |
| [When not to retry](when-not-to-retry.md) | Avoid retrying permanent or unsafe failures |

## Reference

| Reference | Purpose |
|---|---|
| [Public API](api-reference.md) | High-level stable import and method overview |
| [Compatibility policy](reference/compatibility.md) | Supported Python versions and API stability rules |
| [Events](events.md) | Event names, order, and observable fields |
| [TryAgain](try-again.md) | Explicitly request another attempt from application code |

## Maintainers

| Document | Purpose |
|---|---|
| [Architecture](development/architecture.md) | Module responsibilities and dependency boundaries |
| [Design principles](design-principles.md) | Values that guide implementation decisions |
| [Development](development.md) | Set up the project and run local checks |
| [Release process](release.md) | Validate and publish a release |
| [Roadmap](roadmap.md) | Planned project direction |

## Recommended learning path

1. Read [Getting started](getting-started.md).
2. Read [Retry lifecycle](concepts/retry-lifecycle.md).
3. Build a policy with [Policy builder](policy-builder.md).
4. Review [Exhaustion behavior](concepts/exhaustion.md).
5. Use [Diagnostics and guidance](diagnostics.md) and the [Production checklist](production-checklist.md) before deployment.
