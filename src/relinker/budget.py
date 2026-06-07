"""Process-local shared retry budgets.

A retry budget limits additional attempts across executions that share the same
``RetryBudget`` object and key. It is intentionally not a general-purpose rate
limiter: it only reserves times at which Relinker may perform retry attempts.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right, insort
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
            insort(planned, candidate)
        return available

    def _first_legal_slot(self, candidate: float, scheduled_times: list[float]) -> float:
        # Existing reservations are already legal. Any consecutive block of
        # ``max_retries`` reservations inside one period creates an open interval
        # where an additional candidate would overfill some rolling window.
        for index in range(0, len(scheduled_times) - self._max_retries + 1):
            first = scheduled_times[index]
            last = scheduled_times[index + self._max_retries - 1]
            if last - first >= self._per:
                continue
            forbidden_start = last - self._per
            forbidden_end = first + self._per
            if forbidden_start < candidate < forbidden_end:
                candidate = forbidden_end
        # Float rounding can place `candidate` exactly on a boundary where
        # `candidate - per` rounds to a value less than an existing reservation,
        # making the slot illegal according to _is_legal_slot.  Advance by one
        # ULP until the candidate is genuinely legal.
        while not self._is_legal_slot(candidate, scheduled_times):
            candidate = math.nextafter(candidate, math.inf)
        return candidate

    def _is_legal_slot(self, candidate: float, scheduled_times: list[float]) -> bool:
        """Return True when adding ``candidate`` keeps every rolling window in budget."""
        # Existing reservations are already legal. Adding one reservation can only
        # break windows that contain the candidate, so only those window endings
        # need to be checked.
        future_start = bisect_right(scheduled_times, candidate)
        future_end = bisect_left(scheduled_times, candidate + self._per)
        window_ends = (candidate, *scheduled_times[future_start:future_end])
        for window_end in window_ends:
            left = bisect_right(scheduled_times, window_end - self._per)
            right = bisect_right(scheduled_times, window_end)
            if right - left >= self._max_retries:
                return False
        return True
