from __future__ import annotations

import logging

from examples.fake_services import FlakyService
from retryflow import RetryPolicy

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

service = FlakyService(failures_before_success=2)
policy = (
    RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(0.1).with_logging(level=logging.INFO)
)


if __name__ == "__main__":
    print(policy.run(service.call))
