from __future__ import annotations

from examples.fake_services import FlakyService
from retryflow import database

service = FlakyService(failures_before_success=2, error_type=ConnectionError)
policy = database(ConnectionError).with_sleep(lambda seconds: None)


@policy
def save_order() -> str:
    return service.call()


if __name__ == "__main__":
    print(save_order())
    print(save_order.retry_stats.to_dict())
