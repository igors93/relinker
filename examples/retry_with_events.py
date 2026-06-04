from __future__ import annotations

from examples.fake_services import FlakyService
from relinker import RetryEvent, RetryPolicy

service = FlakyService(failures_before_success=2)


def on_retry(event: RetryEvent) -> None:
    print(f"retry after attempt {event.attempt_number}; next delay={event.delay}")


def on_giveup(event: RetryEvent) -> None:
    print(f"giving up after attempt {event.attempt_number}")


policy = (
    RetryPolicy()
    .attempts(3)
    .on(TimeoutError)
    .fixed_delay(0.1)
    .on_retry(on_retry)
    .on_giveup(on_giveup)
)


if __name__ == "__main__":
    print(policy.run(service.call))
