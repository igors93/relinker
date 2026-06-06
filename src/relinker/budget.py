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
        current = _monotonic()
        with self._lock:
            reservations = self._reservations.get(key)
            if reservations is None:
                active = 0
            else:
                boundary = current - self._per
                active = sum(1 for r in reservations if r.scheduled_at > boundary)
        available = max(0, self._max_retries - active)
        return RetryBudgetSnapshot(
            key=key,
            capacity=self._max_retries,
            per=self._per,
            active=active,
            available=available,
        )

    def _reserve(
        self,
        key: str,
        *,
        current_time: float,
        not_before: float,
    ) -> _RetryReservation:
        """Atomically reserve one retry time no earlier than ``not_before``."""
        if not isinstance(key, str) or not key.strip():
            raise InvalidRetryConfigError("retry budget key must be a non-empty string")

        with self._lock:
            reservations = self._reservations.setdefault(key, deque())
            current = float(current_time)
            candidate = max(current, float(not_before))
            self._prune(reservations, current)

            while True:
                boundary = candidate - self._per
                active = [item for item in reservations if item.scheduled_at > boundary]
                if len(active) < self._max_retries:
                    break
                candidate = max(candidate, min(r.scheduled_at for r in active) + self._per)

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
