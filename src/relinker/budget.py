"""Process-local shared retry budgets.

A retry budget limits additional attempts across executions that share the same
``RetryBudget`` object and key. It is intentionally not a general-purpose rate
limiter: it only reserves times at which Relinker may perform retry attempts.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic as _monotonic

from relinker.exceptions import InvalidRetryConfigError
from relinker.internal.validation import ensure_positive, ensure_positive_int


@dataclass(frozen=True, slots=True)
class RetryBudgetSnapshot:
    """Read-only point-in-time view of one budget key's state."""

    key: str
    capacity: int
    per: float
    active: int
    available: int
    queued: int = 0
    next_available_in: float = 0.0

    @property
    def available_now(self) -> int:
        """Return capacity available for immediate reservation."""
        return self.available


@dataclass(frozen=True, slots=True)
class _RetryReservation:
    """One internally reserved retry slot."""

    token: int
    key: str
    scheduled_at: float


class RetryBudget:
    """Limit shared retry attempts within a rolling period.

    The budget is in-memory and process-local. Capacity is shared only by
    policies that reference the same object and use the same key.
    """

    def __init__(self, max_retries: int, *, per: float) -> None:
        ensure_positive_int("max_retries", max_retries)
        ensure_positive("per", per)
        self._max_retries = max_retries
        self._per = float(per)
        self._lock = Lock()
        self._reservations: dict[str, deque[_RetryReservation]] = {}
        self._next_token = 1

    @property
    def max_retries(self) -> int:
        """Return the maximum retries allowed in one rolling period."""
        return self._max_retries

    @property
    def per(self) -> float:
        """Return the rolling period in seconds."""
        return self._per

    def snapshot(self, key: str) -> RetryBudgetSnapshot:
        """Return a read-only point-in-time view of the budget state for *key*."""
        self._validate_key(key)
        current = _monotonic()
        with self._lock:
            reservations = self._reservations.get(key)
            if reservations is None:
                active = 0
                queued = 0
                available = self._max_retries
                next_available_in = 0.0
            else:
                self._prune(reservations, current)
                scheduled_times = sorted(item.scheduled_at for item in reservations)
                active = sum(
                    1
                    for scheduled_at in scheduled_times
                    if current - self._per < scheduled_at <= current
                )
                queued = sum(1 for scheduled_at in scheduled_times if scheduled_at > current)
                available = self._available_at(current, scheduled_times)
                next_available = self._first_legal_slot(current, scheduled_times)
                next_available_in = max(0.0, next_available - current)
        return RetryBudgetSnapshot(
            key=key,
            capacity=self._max_retries,
            per=self._per,
            active=active,
            available=available,
            queued=queued,
            next_available_in=next_available_in,
        )

    def _reserve(
        self,
        key: str,
        *,
        current_time: float,
        not_before: float,
    ) -> _RetryReservation:
        """Atomically reserve one retry time no earlier than ``not_before``."""
        self._validate_key(key)

        with self._lock:
            reservations = self._reservations.setdefault(key, deque())
            current = float(current_time)
            candidate = max(current, float(not_before))
            self._prune(reservations, current)
            scheduled_times = sorted(item.scheduled_at for item in reservations)
            candidate = self._first_legal_slot(candidate, scheduled_times)

            reservation = _RetryReservation(
                token=self._next_token,
                key=key,
                scheduled_at=candidate,
            )
            self._next_token += 1
            reservations.append(reservation)
            return reservation

    def _release(self, reservation: _RetryReservation) -> None:
        """Release one unused reservation; repeated cleanup is harmless."""
        with self._lock:
            reservations = self._reservations.get(reservation.key)
            if not reservations:
                return

            for index, current in enumerate(reservations):
                if current.token == reservation.token:
                    del reservations[index]
                    break

            if not reservations:
                self._reservations.pop(reservation.key, None)

    def _prune(
        self,
        reservations: deque[_RetryReservation],
        candidate: float,
    ) -> None:
        """Remove slots that are outside the rolling period at ``candidate``."""
        boundary = candidate - self._per
        keep = [r for r in reservations if r.scheduled_at > boundary]
        reservations.clear()
        reservations.extend(keep)

    def _validate_key(self, key: str) -> None:
        if not isinstance(key, str) or not key.strip():
            raise InvalidRetryConfigError("retry budget key must be a non-empty string")

    def _available_at(self, candidate: float, scheduled_times: list[float]) -> int:
        available = 0
        planned = list(scheduled_times)
        while self._is_legal_slot(candidate, planned):
            available += 1
            planned.append(candidate)
        return available

    def _first_legal_slot(self, candidate: float, scheduled_times: list[float]) -> float:
        # Evaluate the complete rolling-window invariant. Future reservations only
        # block the candidate when both could appear in the same ``per`` window.
        while not self._is_legal_slot(candidate, scheduled_times):
            candidate = self._next_candidate_after_conflict(candidate, scheduled_times)
        return candidate

    def _is_legal_slot(self, candidate: float, scheduled_times: list[float]) -> bool:
        """Return True when adding ``candidate`` keeps every rolling window in budget."""
        combined = sorted((*scheduled_times, candidate))
        for window_end in combined:
            count = sum(
                1
                for scheduled_at in combined
                if window_end - self._per < scheduled_at <= window_end
            )
            if count > self._max_retries:
                return False
        return True

    def _next_candidate_after_conflict(
        self,
        candidate: float,
        scheduled_times: list[float],
    ) -> float:
        """Move to the next boundary where an existing reservation leaves a window."""
        next_candidates = [
            scheduled_at + self._per
            for scheduled_at in scheduled_times
            if scheduled_at + self._per > candidate
        ]
        if not next_candidates:
            return candidate + self._per
        return min(next_candidates)
