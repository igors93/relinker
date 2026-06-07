"""Regression tests: rolling-window capacity invariant with decimal period values.

The invariant: for any set of scheduled_at times produced by _reserve, no
rolling window of length `per` contains more than `max_retries` reservations.

Window definition (open left, closed right):
    window_end - per < scheduled_at <= window_end

Two float-boundary failure modes are covered:

1. `first + per` rounds such that `(first + per) - per < first`, placing an
   existing reservation inside the new window.

2. A candidate lands exactly on a boundary value that `_first_legal_slot`'s
   strict-inequality check does not advance, causing the post-loop validation
   to walk one representable float at a time until a genuinely legal slot is
   found while the budget lock is held.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from relinker import RetryBudget

ROOT = Path(__file__).resolve().parents[2]


def _assert_rolling_window_capacity(times: list[float], *, capacity: int, per: float) -> None:
    for window_end in times:
        count = sum(1 for scheduled_at in times if window_end - per < scheduled_at <= window_end)
        assert count <= capacity, (
            f"Capacity {capacity} exceeded at window_end={window_end}: "
            f"count={count}, per={per}, times={times}"
        )


def test_decimal_period_boundary_preserves_rolling_window_capacity() -> None:
    """_reserve with per=0.4 must not place two reservations in the same window."""
    budget = RetryBudget(max_retries=1, per=0.4)

    reservations = [
        budget._reserve("api", current_time=0.0, not_before=0.1),
        budget._reserve("api", current_time=0.0, not_before=0.0),
    ]
    times = [r.scheduled_at for r in reservations]

    _assert_rolling_window_capacity(times, capacity=budget.max_retries, per=budget.per)


@pytest.mark.parametrize(
    ("max_retries", "per", "not_befores"),
    [
        (1, 0.4, [0.1, 0.0]),
        (1, 0.1, [0.05, 0.0]),
        (1, 0.3, [0.1, 0.0]),
        (2, 0.4, [0.1, 0.2, 0.0]),
    ],
)
def test_decimal_period_capacity_invariant_parametrized(
    max_retries: int,
    per: float,
    not_befores: list[float],
) -> None:
    """Capacity invariant holds for several decimal period / not_before combinations."""
    budget = RetryBudget(max_retries=max_retries, per=per)
    reservations = [budget._reserve("api", current_time=0.0, not_before=nb) for nb in not_befores]
    times = [r.scheduled_at for r in reservations]

    for r, nb in zip(reservations, not_befores, strict=True):
        assert r.scheduled_at >= nb, f"scheduled_at={r.scheduled_at} < not_before={nb}"

    _assert_rolling_window_capacity(times, capacity=budget.max_retries, per=budget.per)


_ULP_WALK_SCENARIO = """\
from relinker import RetryBudget
budget = RetryBudget(max_retries=2, per=0.4)
for not_before in (1.0, 1.8, 1.0, 1.0, 2.6):
    budget._reserve("api", current_time=1.0, not_before=not_before)
budget._reserve("api", current_time=1.0, not_before=1.4)
print("ok")
"""


_DECIMAL_BOUNDARY_SCENARIO = """\
from relinker import RetryBudget


def assert_rolling_window_capacity(times, *, capacity, per):
    for window_end in times:
        count = sum(1 for scheduled_at in times if window_end - per < scheduled_at <= window_end)
        assert count <= capacity, (window_end, count, times)


budget = RetryBudget(max_retries=2, per=0.4)
reservations = [
    budget._reserve("api", current_time=0.0, not_before=0.1),
    budget._reserve("api", current_time=0.0, not_before=0.5),
    budget._reserve("api", current_time=0.0, not_before=0.4),
]
times = [reservation.scheduled_at for reservation in reservations]

assert reservations[-1].scheduled_at >= 0.4
assert_rolling_window_capacity(times, capacity=budget.max_retries, per=budget.per)
print("ok")
"""


def _run_budget_subprocess(
    script: str,
    *,
    timeout: float = 5.0,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    pythonpath_entries = [str(ROOT / "src")]
    if env.get("PYTHONPATH"):
        pythonpath_entries.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)

    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=ROOT,
        env=env,
    )


def test_decimal_boundary_subprocess_completes_and_preserves_capacity() -> None:
    """A decimal boundary candidate must terminate and preserve window capacity."""
    result = _run_budget_subprocess(_DECIMAL_BOUNDARY_SCENARIO)
    assert result.returncode == 0, (
        f"subprocess failed or timed out.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert result.stdout.strip() == "ok"


def test_boundary_exact_candidate_completes_without_ulp_walk() -> None:
    """_reserve must terminate promptly when a candidate lands on an exact boundary.

    The scenario builds a state where candidate=1.4 falls exactly on a
    forbidden-region boundary that the strict-inequality check in
    _first_legal_slot does not advance.  The previous ULP-by-ULP fallback
    advanced one representable float at a time and did not complete within the
    timeout.

    This test runs the scenario in a subprocess with a 5-second timeout.
    Termination verifies the invariant: _first_legal_slot must jump directly
    to the next relevant boundary rather than walking ULP-by-ULP.
    """
    result = _run_budget_subprocess(_ULP_WALK_SCENARIO)
    assert result.returncode == 0, (
        f"subprocess failed or timed out.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert result.stdout.strip() == "ok"


def test_boundary_forced_slot_is_minimal() -> None:
    """When _reserve advances a candidate off a forbidden boundary, the result
    is the earliest legal float: the immediately preceding float must be illegal.

    This confirms that the fix does not overshoot — it uses the smallest
    advancement needed to satisfy the rolling-window invariant.
    """
    budget = RetryBudget(max_retries=1, per=0.4)
    # First reservation at 0.1 fills the window (−0.3, 0.5].
    # Second candidate 0.0 must be pushed to the first float ≥ 0.5 that is legal.
    first = budget._reserve("api", current_time=0.0, not_before=0.1)
    second = budget._reserve("api", current_time=0.0, not_before=0.0)

    result = second.scheduled_at
    previous = math.nextafter(result, -math.inf)

    # The result must be legal.
    times_with_result = [first.scheduled_at, result]
    _assert_rolling_window_capacity(times_with_result, capacity=budget.max_retries, per=budget.per)

    # The immediately preceding float must be illegal (minimality).
    times_with_previous = [first.scheduled_at, previous]
    violations = [
        window_end
        for window_end in times_with_previous
        if sum(1 for s in times_with_previous if window_end - budget.per < s <= window_end)
        > budget.max_retries
    ]
    assert violations, (
        f"Expected math.nextafter({result}, -inf) = {previous} to be illegal "
        f"(capacity-violating), but no window was overfull. "
        f"The returned slot may not be minimal."
    )


def test_rounded_up_boundary_does_not_skip_earliest_legal_float() -> None:
    """The selected slot must be legal and no earlier legal float may be skipped."""
    budget = RetryBudget(max_retries=1, per=0.3)
    not_before = 0.6

    first = budget._reserve(
        "api",
        current_time=0.0,
        not_before=0.5000000000000002,
    )
    second = budget._reserve(
        "api",
        current_time=0.0,
        not_before=not_before,
    )

    result = second.scheduled_at
    previous = math.nextafter(result, -math.inf)

    assert result >= not_before
    assert budget._is_legal_slot(result, [first.scheduled_at])
    assert previous < not_before or not budget._is_legal_slot(previous, [first.scheduled_at])
