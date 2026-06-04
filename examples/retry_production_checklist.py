"""
Example: Production policy review using diagnostics.

Before deploying a retry policy, use warnings() and simulate() to check
for common issues. This script shows how to build a pre-deploy checker.
"""

from __future__ import annotations

from retryflow import RetryPolicy


def review_policy(name: str, policy: RetryPolicy) -> None:  # type: ignore[type-arg]
    """Print a diagnostics review for a policy."""
    print(f"\n{'=' * 50}")
    print(f"Policy: {name}")
    print(policy.explain())

    warnings = policy.warnings()
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  [{w.code}] {w.message}")
            if w.hint:
                print(f"    Hint: {w.hint}")
    else:
        print("\nNo warnings.")

    print("\nSimulation (5 attempts):")
    sim = policy.simulate(attempts=5)
    print(f"  Attempt count: {sim.attempt_count}")
    print(f"  Total sleep: {sim.total_sleep:.3f}s")
    print(f"  Max delay: {sim.max_delay:.3f}s")
    print(f"  Stops early: {sim.stops_early}")


# --- Policies to review ---

FAST_API = (
    RetryPolicy()
    .attempts(3)
    .on(ConnectionError, TimeoutError)
    .exponential_delay(base=0.1, factor=2, maximum=1.0)
    .jitter(maximum=0.1)
)

RISKY_POLICY = RetryPolicy().forever().on(Exception).no_delay()

BACKGROUND_WORKER = (
    RetryPolicy().attempts(10).on(Exception).exponential_delay(base=0.5, factor=2, maximum=30)
)

WELL_CONFIGURED = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError, ConnectionError)
    .exponential_delay(base=0.5, maximum=10)
    .jitter(maximum=0.5)
    .return_result()
)


if __name__ == "__main__":
    review_policy("Fast API client", FAST_API)
    review_policy("Risky policy (do not ship)", RISKY_POLICY)
    review_policy("Background worker", BACKGROUND_WORKER)
    review_policy("Well-configured policy", WELL_CONFIGURED)
