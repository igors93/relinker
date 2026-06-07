"""Measure RetryBudget reservation cost for development diagnostics.

This script is intentionally not part of the test suite. It prints timing data
without enforcing machine-dependent thresholds.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from statistics import mean
from time import perf_counter

from relinker import RetryBudget


def _reserve_many(*, count: int, capacity: int, out_of_order: bool) -> tuple[float, float]:
    budget = RetryBudget(max_retries=capacity, per=10)
    if out_of_order:
        not_befores = [float((index * 7) % max(1, count)) for index in range(count)]
    else:
        not_befores = [float(index) for index in range(count)]

    started = perf_counter()
    for not_before in not_befores:
        budget._reserve("api", current_time=0, not_before=not_before)
    elapsed = perf_counter() - started
    return elapsed, elapsed / count


def _reserve_concurrently(*, count: int, capacity: int) -> tuple[float, float]:
    budget = RetryBudget(max_retries=capacity, per=10)
    not_befores = [float((index * 7) % max(1, count)) for index in range(count)]

    def reserve(not_before: float) -> float:
        return budget._reserve("api", current_time=0, not_before=not_before).scheduled_at

    started = perf_counter()
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(reserve, not_befores))
    elapsed = perf_counter() - started
    return elapsed, elapsed / count


def main() -> None:
    print("RetryBudget reservation benchmark")
    print("No thresholds are enforced; compare results across local runs.\n")
    for count in (100, 1_000, 5_000):
        for capacity in (1, 10):
            rows: list[tuple[str, float, float]] = []
            for label, out_of_order in (("ordered", False), ("out_of_order", True)):
                elapsed, per_reservation = _reserve_many(
                    count=count,
                    capacity=capacity,
                    out_of_order=out_of_order,
                )
                rows.append((label, elapsed, per_reservation))
            elapsed, per_reservation = _reserve_concurrently(count=count, capacity=capacity)
            rows.append(("concurrent_8_workers", elapsed, per_reservation))

            average = mean(per_reservation for _label, _elapsed, per_reservation in rows)
            print(f"reservations={count} capacity={capacity} avg={average:.8f}s/reservation")
            for label, elapsed, per_reservation in rows:
                print(f"  {label:20s} total={elapsed:.4f}s per={per_reservation:.8f}s")
            print()


if __name__ == "__main__":
    main()
