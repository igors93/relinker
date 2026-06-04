from __future__ import annotations

from examples.fake_services import FlakyService
from retryflow import retry

service = FlakyService(failures_before_success=2)


@retry(attempts=3, delay=0.1, on=(TimeoutError,))
def fetch_data() -> str:
    return service.call()


if __name__ == "__main__":
    print(fetch_data())
    print(f"calls: {service.calls}")
