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

# Amortized cleanup: scan for expired keys every N lock-guarded operations.
_CLEANUP_INTERVAL = 100


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
        self._op_count = 0

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
            self._maybe_cleanup(current)
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
            current = float(current_time)
            candidate = max(current, float(not_before))
            self._maybe_cleanup(current)
            reservations = self._reservations.setdefault(key, deque())
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
        current_time = _monotonic()
        with self._lock:
            self._maybe_cleanup(current_time)
            reservations = self._reservations.get(reservation.key)
            if not reservations:
                return

            for index, item in enumerate(reservations):
                if item.token == reservation.token:
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

    def cleanup(self) -> None:
        """Remove all keys with no active or future reservations.

        Relinker performs incremental cleanup automatically. Call this when you
        want to release memory immediately, for example at the end of a request
        or a maintenance job.
        """
        current = _monotonic()
        with self._lock:
            self._cleanup_expired_keys(current)

    def _cleanup_expired_keys(self, current: float) -> None:
        """Remove keys whose every reservation has expired. Must be called under the lock."""
        boundary = current - self._per
        expired_keys = [
            key
            for key, reservations in self._reservations.items()
            if not reservations or all(r.scheduled_at <= boundary for r in reservations)
        ]
        for key in expired_keys:
            del self._reservations[key]

    def _maybe_cleanup(self, current: float) -> None:
        """Amortized cleanup: remove fully-expired keys every _CLEANUP_INTERVAL operations.

        Must be called under the lock. Does not hold the lock during any external code
        or I/O — only pure dictionary iteration is performed.
        """
        self._op_count += 1
        if self._op_count >= _CLEANUP_INTERVAL:
            self._op_count = 0
            self._cleanup_expired_keys(current)

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
        # ``max_retries`` reservations inside one period creates an interval
        # where an additional candidate would overfill some rolling window.
        #
        # Keep this detection consistent with _is_legal_slot(): both use the
        # same open-left boundary expression, ``window_end - per``. Decimal
        # periods can make ``last - first == per`` while ``last - per < first``,
        # so checking the subtraction in the opposite order is not equivalent.
        #
        # Re-scan after each advance: moving candidate to one boundary may place
        # it inside a different forbidden region.
        changed = True
        while changed:
            changed = False
            for index in range(0, len(scheduled_times) - self._max_retries + 1):
                first = scheduled_times[index]
                last = scheduled_times[index + self._max_retries - 1]
                forbidden_start = last - self._per
                if first <= forbidden_start:
                    continue
                forbidden_end = self._first_slot_after_window(first)
                if forbidden_start < candidate < forbidden_end:
                    candidate = forbidden_end
                    changed = True
        return candidate

    def _first_slot_after_window(self, first: float) -> float:
        """Return the first float whose open-left window boundary excludes ``first``."""
        candidate = first + self._per
        previous = math.nextafter(candidate, -math.inf)
        if previous - self._per >= first:
            return previous
        if candidate - self._per >= first:
            return candidate
        return math.nextafter(candidate, math.inf)

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
