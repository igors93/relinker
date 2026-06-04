from __future__ import annotations

from examples.fake_services import FlakyService
from relinker import RetryPolicy

service = FlakyService(failures_before_success=2)

policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(0.1).return_result()


if __name__ == "__main__":
    result = policy.run(service.call)
    print(result.summary())
    print()
    print(result.story())
