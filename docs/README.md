# Relinker Documentation

**Simple by default, powerful by composition, safe by guidance.**

This directory is organized by intent:

- `guides/` explains how to use Relinker in application code.
- `concepts/` explains core runtime behavior and mental models.
- `reference/` lists public API and compatibility details.
- `maintainers/` documents project internals and release work.

## Start here

| Guide | Purpose |
|---|---|
| [Getting started](guides/getting-started.md) | Install Relinker and run a first retry policy |
| [Installation](guides/installation.md) | Install from PyPI, GitHub, or source |
| [Policy builder](guides/policy-builder.md) | Learn the fluent, immutable `RetryPolicy` API |
| [Production checklist](guides/production-checklist.md) | Review a policy before deploying it |

## Core concepts

| Concept | Purpose |
|---|---|
| [Retry lifecycle](concepts/retry-lifecycle.md) | Understand one execution from first call to final outcome |
| [Exhaustion behavior](concepts/exhaustion.md) | Choose what happens when another retry is no longer allowed |
| [Retry budgets](concepts/retry-budgets.md) | Share process-local retry capacity during incidents |
| [Results and statistics](concepts/results.md) | Inspect final outcomes and aggregate counters |
| [Runtime state](concepts/state.md) | Understand the immutable state exposed to hooks and delays |

## Usage guides

| Guide | Purpose |
|---|---|
| [Async execution](guides/async.md) | Retry coroutine functions safely |
| [Context manager usage](guides/context-manager.md) | Retry inline sync and async blocks |
| [HTTP retry](guides/http.md) | Retry status codes and respect `Retry-After` |
| [Observability](guides/observability.md) | Use logging, structured logging, and events |
| [Diagnostics and guidance](guides/diagnostics.md) | Use warnings, doctor, preview, and explain |
| [Testing retry code](guides/testing.md) | Keep tests deterministic and avoid real sleeping |
| [Common patterns](guides/common-patterns.md) | Apply Relinker to recurring application scenarios |
| [Safety](guides/safety.md) | Review built-in safety guidance |
| [When not to retry](guides/when-not-to-retry.md) | Avoid retrying permanent or unsafe failures |
| [Examples](guides/examples.md) | Find runnable example scripts |

## Reference

| Reference | Purpose |
|---|---|
| [Public API](reference/api.md) | High-level stable import and method overview |
| [Compatibility policy](reference/compatibility.md) | Supported Python versions and API stability rules |
| [Delays](reference/delays.md) | Delay strategy details |
| [Presets](reference/presets.md) | Built-in preset policies |
| [Events](reference/events.md) | Event names, order, and observable fields |
| [TryAgain](reference/try-again.md) | Explicitly request another attempt from application code |

## Maintainers

| Document | Purpose |
|---|---|
| [Architecture](maintainers/architecture.md) | Module responsibilities and dependency boundaries |
| [Design principles](maintainers/design-principles.md) | Values that guide implementation decisions |
| [Development](maintainers/development.md) | Set up the project and run local checks |
| [Release process](maintainers/release.md) | Validate and publish a release |

## Recommended learning path

1. Read [Getting started](guides/getting-started.md).
2. Read [Retry lifecycle](concepts/retry-lifecycle.md).
3. Build a policy with [Policy builder](guides/policy-builder.md).
4. Review [Exhaustion behavior](concepts/exhaustion.md).
5. Use [Diagnostics and guidance](guides/diagnostics.md) and the [Production checklist](guides/production-checklist.md) before deployment.
