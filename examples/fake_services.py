from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FlakyService:
    failures_before_success: int
    error_type: type[Exception] = TimeoutError
    calls: int = 0

    def call(self) -> str:
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise self.error_type(f"temporary failure #{self.calls}")
        return "ok"


@dataclass
class FakeResponse:
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""


@dataclass
class StatusSequence:
    responses: list[FakeResponse]
    calls: int = 0

    def call(self) -> FakeResponse:
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[index]
