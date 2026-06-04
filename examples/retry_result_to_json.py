from __future__ import annotations

from examples.fake_services import FlakyService
from retryflow import RetryPolicy

service = FlakyService(failures_before_success=1)
policy = RetryPolicy().attempts(3).on(TimeoutError).return_result()


if __name__ == "__main__":
    result = policy.run(service.call)
    print(result.to_json(indent=2))
