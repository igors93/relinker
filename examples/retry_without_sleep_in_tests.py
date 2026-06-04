from __future__ import annotations

from examples.fake_services import FlakyService
from relinker import RetryPolicy

sleeps: list[float] = []
service = FlakyService(failures_before_success=2)

policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(10).with_sleep(sleeps.append)


if __name__ == "__main__":
    print(policy.run(service.call))
    print(f"requested sleeps: {sleeps}")
