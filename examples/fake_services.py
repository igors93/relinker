"""
Fake services for RetryFlow examples.

These helpers simulate realistic failure modes — transient errors, slow
responses, and pending states — without any real network calls or dependencies.
They are reused across other example scripts.
"""

from __future__ import annotations

import random


class UnstableHTTPClient:
    """Simulates an HTTP client that fails a fixed number of times."""

    def __init__(self, *, fail_times: int = 2, status: int = 200) -> None:
        self._fail_times = fail_times
        self._calls = 0
        self._status = status

    def get(self, url: str) -> dict[str, object]:
        self._calls += 1
        if self._fail_times > 0:
            self._fail_times -= 1
            raise ConnectionError(f"connection refused on call {self._calls} to {url}")
        return {"status_code": self._status, "body": "ok", "calls": self._calls}

    @property
    def calls(self) -> int:
        return self._calls


class UnstableDatabase:
    """Simulates a database connection that times out occasionally."""

    def __init__(self, *, timeout_times: int = 1) -> None:
        self._timeout_times = timeout_times
        self._calls = 0

    def query(self, sql: str) -> list[dict[str, object]]:
        self._calls += 1
        if self._timeout_times > 0:
            self._timeout_times -= 1
            raise TimeoutError(f"query timed out on attempt {self._calls}: {sql}")
        return [{"id": 1, "value": "row", "call": self._calls}]

    @property
    def calls(self) -> int:
        return self._calls


class PollableJob:
    """Simulates a background job that takes a few polls before completing."""

    def __init__(self, *, polls_needed: int = 3) -> None:
        self._polls_left = polls_needed
        self._polls = 0

    def status(self) -> str:
        self._polls += 1
        if self._polls_left > 0:
            self._polls_left -= 1
            return "pending"
        return "completed"

    @property
    def polls(self) -> int:
        return self._polls


class FlappyService:
    """Simulates a service that randomly fails with configurable probability."""

    def __init__(self, *, fail_probability: float = 0.5, seed: int = 42) -> None:
        self._probability = fail_probability
        self._rng = random.Random(seed)
        self._calls = 0

    def call(self) -> str:
        self._calls += 1
        if self._rng.random() < self._probability:
            raise OSError(f"service flapped on call {self._calls}")
        return f"success on call {self._calls}"

    @property
    def calls(self) -> int:
        return self._calls
