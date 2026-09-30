"""Combine normal policy delays with shared retry-budget reservations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from relinker.budget import RetryBudget, _RetryReservation
from relinker.delays.stateful import resolve_delay
from relinker.internal import clock
from relinker.internal.validation import MAX_SLEEP_SECONDS, ensure_resolved_delay

if TYPE_CHECKING:
    from relinker.policy import RetryPolicy
    from relinker.state import RetryState


@dataclass(frozen=True, slots=True)
class RetryWaitPlan:
    """Resolved wait before one additional attempt."""

    policy_delay: float
    budget_delay: float
    total_delay: float
    reservation: _RetryReservation | None = None
    budget: RetryBudget | None = None


def plan_retry_wait(
    policy: RetryPolicy[Any],
    attempt_number: int,
    state: RetryState | None,
) -> RetryWaitPlan | None:
    """Resolve policy delay and, when configured, reserve shared retry capacity.

    Returns ``None`` when the shared retry budget cannot schedule the retry
    within ``MAX_SLEEP_SECONDS``. That is an operational condition (the budget
    is saturated), not a configuration error, so callers give up as exhausted.
    No reservation is left behind in that case or when planning fails.
    """
    policy_delay = ensure_resolved_delay(
        resolve_delay(policy.delay_strategy, attempt_number, state)
    )
    budget = policy.retry_budget
    if budget is None:
        return RetryWaitPlan(
            policy_delay=policy_delay,
            budget_delay=0.0,
            total_delay=policy_delay,
        )

    key = policy.retry_budget_key
    if key is None:  # Defensive guard; public policy construction prevents this.
        raise RuntimeError("retry budget configured without a key")

    current_time = clock.now()
    not_before = current_time + policy_delay
    reservation = budget._reserve(
        key,
        current_time=current_time,
        not_before=not_before,
    )
    try:
        budget_delay = max(0.0, reservation.scheduled_at - not_before)
        total_delay = policy_delay + budget_delay
        if total_delay > MAX_SLEEP_SECONDS:
            budget._release(reservation)
            return None
        return RetryWaitPlan(
            policy_delay=policy_delay,
            budget_delay=ensure_resolved_delay(budget_delay),
            total_delay=ensure_resolved_delay(total_delay),
            reservation=reservation,
            budget=budget,
        )
    except BaseException:
        budget._release(reservation)
        raise


def release_retry_wait(plan: RetryWaitPlan) -> None:
    """Release the reservation in ``plan`` when the planned retry will not run."""
    if plan.budget is not None and plan.reservation is not None:
        plan.budget._release(plan.reservation)
