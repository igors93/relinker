from __future__ import annotations

from examples.fake_services import FlakyService
from relinker import retry

service = FlakyService(failures_before_success=1)


@retry(attempts=3, delay=0.1, on=(TimeoutError,))
def fetch_data() -> str:
    return service.call()


if __name__ == "__main__":
    print(fetch_data())
    print(fetch_data.retry_stats.to_dict())
