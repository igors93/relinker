"""Measure RetryBudget costs for development diagnostics.

This script is intentionally not a normal test-suite gate. It prints local
timing and memory data without enforcing machine-dependent thresholds.
"""

from __future__ import annotations

import argparse
import tracemalloc
from collections.abc import Iterable
from dataclasses import dataclass
from statistics import mean
from time import perf_counter

from relinker import RetryBudget
from relinker.budget import _RetryReservation


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    scenario: str
    count: int
    capacity: int
    total_seconds: float
    per_operation_seconds: float
    peak_kib: float


def _not_befores(count: int, *, capacity: int, scenario: str) -> list[float]:
    if scenario == "ordered":
        return [float(index) for index in range(count)]
    if scenario == "future":
        return [float(count + index) for index in range(count)]
    if scenario == "decimal":
        return [((index * 7) % max(1, capacity * 3)) * 0.1 for index in range(count)]
    if scenario == "multi_key":
        return [float(index % max(1, capacity)) for index in range(count)]
    raise ValueError(f"unknown scenario: {scenario}")


def _measure(
    scenario: str,
    count: int,
    capacity: int,
    operation: str,
) -> BenchmarkResult:
    tracemalloc.start()
    started = perf_counter()
    _run_operation(scenario=scenario, count=count, capacity=capacity, operation=operation)
    total = perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return BenchmarkResult(
        scenario=f"{scenario}/{operation}",
        count=count,
        capacity=capacity,
        total_seconds=total,
        per_operation_seconds=total / max(1, count),
        peak_kib=peak / 1024,
    )


def _run_operation(
    *,
    scenario: str,
    count: int,
    capacity: int,
    operation: str,
) -> None:
    if operation == "reserve":
        _reserve_many(scenario=scenario, count=count, capacity=capacity)
    elif operation == "release":
        _release_many(scenario=scenario, count=count, capacity=capacity)
    elif operation == "snapshot":
        _snapshot_many(scenario=scenario, count=count, capacity=capacity)
    else:
        raise ValueError(f"unknown operation: {operation}")


def _reserve_many(*, scenario: str, count: int, capacity: int) -> list[_RetryReservation]:
    budget = RetryBudget(max_retries=capacity, per=10.0 if scenario != "decimal" else 0.3)
    reservations: list[_RetryReservation] = []
    for index, not_before in enumerate(_not_befores(count, capacity=capacity, scenario=scenario)):
        key = f"api-{index % 10}" if scenario == "multi_key" else "api"
        reservations.append(budget._reserve(key, current_time=0.0, not_before=not_before))
    return reservations


def _release_many(*, scenario: str, count: int, capacity: int) -> None:
    budget = RetryBudget(max_retries=capacity, per=10.0 if scenario != "decimal" else 0.3)
    reservations: list[_RetryReservation] = []
    for index, not_before in enumerate(_not_befores(count, capacity=capacity, scenario=scenario)):
        key = f"api-{index % 10}" if scenario == "multi_key" else "api"
        reservations.append(budget._reserve(key, current_time=0.0, not_before=not_before))

    release_order = (
        reservations[: count // 3]
        + reservations[count // 3 : (2 * count) // 3]
        + reservations[(2 * count) // 3 :]
    )
    for reservation in release_order:
        budget._release(reservation)


def _snapshot_many(*, scenario: str, count: int, capacity: int) -> None:
    budget = RetryBudget(max_retries=capacity, per=10.0 if scenario != "decimal" else 0.3)
    for index, not_before in enumerate(
        _not_befores(min(count, 1_000), capacity=capacity, scenario=scenario)
    ):
        key = f"api-{index % 10}" if scenario == "multi_key" else "api"
        budget._reserve(key, current_time=0.0, not_before=not_before)

    for index in range(count):
        key = f"api-{index % 10}" if scenario == "multi_key" else "api"
        budget.snapshot(key)


def _print_results(results: Iterable[BenchmarkResult]) -> None:
    print("RetryBudget benchmark")
    print("No thresholds are enforced; compare results across local runs.\n")
    grouped: dict[tuple[int, int], list[BenchmarkResult]] = {}
    for result in results:
        grouped.setdefault((result.count, result.capacity), []).append(result)

    for (count, capacity), rows in grouped.items():
        average = mean(row.per_operation_seconds for row in rows)
        print(f"reservations={count} capacity={capacity} avg={average:.8f}s/op")
        for row in rows:
            print(
                f"  {row.scenario:24s} total={row.total_seconds:.4f}s "
                f"per={row.per_operation_seconds:.8f}s peak={row.peak_kib:.1f}KiB"
            )
        print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quick",
        action="store_true",
        help="use smaller counts for local smoke runs",
    )
    args = parser.parse_args()

    counts = (10, 100) if args.quick else (10, 100, 1_000, 10_000)
    capacities = (1, 10) if args.quick else (1, 10, 100)
    scenarios = ("ordered", "future", "decimal", "multi_key")
    operations = ("reserve", "release", "snapshot")

    results = [
        _measure(scenario, count, capacity, operation)
        for count in counts
        for capacity in capacities
        for scenario in scenarios
        for operation in operations
    ]
    _print_results(results)


if __name__ == "__main__":
    main()
