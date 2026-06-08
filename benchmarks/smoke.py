"""Run small non-gating performance smoke measurements for maintainers."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from relinker import RetryBudget, RetryPolicy  # noqa: E402


def _measure(label: str, iterations: int, callback: Callable[[], Any]) -> None:
    started = time.perf_counter()
    for _ in range(iterations):
        callback()
    elapsed = time.perf_counter() - started
    operations_per_second = iterations / elapsed if elapsed else float("inf")

    print(f"{label}: {elapsed:.6f}s total, {operations_per_second:.2f} ops/s")


def _immediate_success() -> str:
    policy = RetryPolicy[str]().attempts(1).no_delay()

    def operation() -> str:
        return "ok"

    return policy.run(operation)


def _one_failure_then_success() -> str:
    calls = 0
    policy = RetryPolicy[str]().attempts(2).on(TimeoutError).no_delay()

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise TimeoutError("temporary")
        return "ok"

    return policy.run(operation)


def _return_result() -> bool:
    policy = RetryPolicy[str]().attempts(1).no_delay().return_result()

    def operation() -> str:
        return "ok"

    result = policy.run(operation)
    return bool(result.succeeded)


def _context_manager() -> str:
    policy = RetryPolicy[str]().attempts(1).no_delay()
    iterator = policy.iter(name="benchmark_context")

    for attempt in iterator:
        with attempt:
            attempt.set_result("ok")

    return "ok"


def _retry_budget() -> str:
    budget = RetryBudget(max_retries=1, per=60)
    policy = (
        RetryPolicy[str]()
        .attempts(2)
        .on(TimeoutError)
        .no_delay()
        .with_retry_budget(budget, key="benchmark")
    )
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise TimeoutError("temporary")
        return "ok"

    return policy.run(operation)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()

    if args.iterations <= 0:
        raise SystemExit("--iterations must be positive")

    _measure("immediate success", args.iterations, _immediate_success)
    _measure("one failure then success", args.iterations, _one_failure_then_success)
    _measure("return_result", args.iterations, _return_result)
    _measure("context manager", args.iterations, _context_manager)
    _measure("retry budget", args.iterations, _retry_budget)


if __name__ == "__main__":
    main()
