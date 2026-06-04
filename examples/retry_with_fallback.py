from __future__ import annotations

from examples.fake_services import FlakyService
from relinker import RetryPolicy

service = FlakyService(failures_before_success=99)

policy = (
    RetryPolicy()
    .attempts(3)
    .on(TimeoutError)
    .fixed_delay(0.1)
    .fallback_value({"status": "offline"})
)


if __name__ == "__main__":
    print(policy.run(service.call))
