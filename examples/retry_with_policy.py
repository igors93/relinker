from __future__ import annotations

from examples.fake_services import FlakyService
from retryflow import RetryPolicy

service = FlakyService(failures_before_success=2)

policy = (
    RetryPolicy()
    .attempts(4)
    .on(TimeoutError)
    .exponential_delay(base=0.1, maximum=1.0)
    .jitter(maximum=0.05)
)


@policy
def fetch_data() -> str:
    return service.call()


if __name__ == "__main__":
    print(policy.explain())
    print(fetch_data())
