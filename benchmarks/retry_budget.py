"""Measure RetryBudget costs for development diagnostics.

This script is intentionally not a normal test-suite gate. It prints local
timing and memory data without enforcing machine-dependent thresholds.
"""

from __future__ import annotations

import argparse
import random
import tracemalloc
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from statistics import mean
from threading import Barrier
from time import monotonic, perf_counter

from relinker import RetryBudget
from relinker.budget import _RetryReservation

RELEASE_OPERATIONS = (
    "release_forward",
    "release_reverse",
    "release_first_repeated_pattern",
    "release_middle_first",
    "release_last_first",
    "release_shuffled",
)
CONCURRENT_RESERVE_OPERATIONS = (
    "concurrent_reserve_8_workers",
    "concurrent_reserve_32_workers",
)


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
    elif operation in RELEASE_OPERATIONS:
        _release_many(
            scenario=scenario,
            count=count,
            capacity=capacity,
            release_operation=operation,
        )
    elif operation == "snapshot":
        _snapshot_many(scenario=scenario, count=count, capacity=capacity)
    elif operation in CONCURRENT_RESERVE_OPERATIONS:
        workers = 8 if operation == "concurrent_reserve_8_workers" else 32
        _concurrent_reserve_many(
            scenario=scenario,
            count=count,
            capacity=capacity,
            workers=workers,
        )
    else:
        raise ValueError(f"unknown operation: {operation}")


def _reserve_many(*, scenario: str, count: int, capacity: int) -> list[_RetryReservation]:
    budget = RetryBudget(max_retries=capacity, per=10.0 if scenario != "decimal" else 0.3)
    reservations: list[_RetryReservation] = []
    for index, not_before in enumerate(_not_befores(count, capacity=capacity, scenario=scenario)):
        key = f"api-{index % 10}" if scenario == "multi_key" else "api"
        reservations.append(budget._reserve(key, current_time=0.0, not_before=not_before))
    return reservations


def _release_order(
    reservations: list[_RetryReservation],
    *,
    release_operation: str,
) -> list[_RetryReservation]:
    if release_operation == "release_forward":
        return list(reservations)
    if release_operation == "release_reverse":
        return list(reversed(reservations))
    if release_operation == "release_first_repeated_pattern":
        return reservations[0::3] + reservations[1::3] + reservations[2::3]
    if release_operation == "release_middle_first":
        middle = len(reservations) // 2
        return reservations[middle:] + reservations[:middle]
    if release_operation == "release_last_first":
        return reservations[-1:] + reservations[:-1]
    if release_operation == "release_shuffled":
        shuffled = list(reservations)
        random.Random(12_020).shuffle(shuffled)
        return shuffled
    raise ValueError(f"unknown release operation: {release_operation}")


def _release_many(
    *,
    scenario: str,
    count: int,
    capacity: int,
    release_operation: str,
) -> None:
    budget = RetryBudget(max_retries=capacity, per=10.0 if scenario != "decimal" else 0.3)
    reservations: list[_RetryReservation] = []
    for index, not_before in enumerate(_not_befores(count, capacity=capacity, scenario=scenario)):
        key = f"api-{index % 10}" if scenario == "multi_key" else "api"
        reservations.append(budget._reserve(key, current_time=0.0, not_before=not_before))

    for reservation in _release_order(reservations, release_operation=release_operation):
        budget._release(reservation)


def _snapshot_many(*, scenario: str, count: int, capacity: int) -> None:
    budget = RetryBudget(max_retries=capacity, per=10.0 if scenario != "decimal" else 0.3)
    base_time = monotonic()
    for index, not_before in enumerate(
        _not_befores(min(count, 1_000), capacity=capacity, scenario=scenario)
    ):
        key = f"api-{index % 10}" if scenario == "multi_key" else "api"
        budget._reserve(key, current_time=base_time, not_before=base_time + not_before)

    for index in range(count):
        key = f"api-{index % 10}" if scenario == "multi_key" else "api"
        budget.snapshot(key)


def _concurrent_reserve_many(
    *,
    scenario: str,
    count: int,
    capacity: int,
    workers: int,
) -> None:
    budget = RetryBudget(max_retries=capacity, per=10.0 if scenario != "decimal" else 0.3)
    not_befores = _not_befores(count, capacity=capacity, scenario=scenario)
    barrier = Barrier(workers)

    def reserve_worker(worker_index: int) -> None:
        barrier.wait(timeout=10)
        for index in range(worker_index, count, workers):
            key = f"api-{index % 10}" if scenario == "multi_key" else "api"
            budget._reserve(key, current_time=0.0, not_before=not_befores[index])

    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(reserve_worker, range(workers)))


def _print_results(results: Iterable[BenchmarkResult]) -> None:
    print("RetryBudget benchmark")
    print("No thresholds are enforced; compare results across local runs.\n")
    print("snapshot scenarios prefill up to 1000 reservations before measurement")
    print("concurrent_reserve scenarios use a ThreadPoolExecutor and Barrier\n")
    grouped: dict[tuple[int, int], list[BenchmarkResult]] = {}
    for result in results:
        grouped.setdefault((result.count, result.capacity), []).append(result)

    for (count, capacity), rows in grouped.items():
        average = mean(row.per_operation_seconds for row in rows)
        print(f"reservations={count} capacity={capacity} avg={average:.8f}s/op")
        for row in rows:
            print(
                f"  {row.scenario:46s} total={row.total_seconds:.4f}s "
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
    operations = (
        "reserve",
        *RELEASE_OPERATIONS,
        "snapshot",
        *CONCURRENT_RESERVE_OPERATIONS,
    )

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
