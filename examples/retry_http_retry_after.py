from __future__ import annotations

from examples.fake_services import FakeResponse, StatusSequence
from retryflow import RetryPolicy, retry_after_delay, retry_if_status

api = StatusSequence(
    [
        FakeResponse(429, headers={"Retry-After": "1"}, body="rate limited"),
        FakeResponse(200, body="ok"),
    ]
)

policy = (
    RetryPolicy()
    .attempts(3)
    .retry_if_result(retry_if_status({429, 503}))
    .stateful_delay(retry_after_delay(default=0.1, maximum=2.0))
)


if __name__ == "__main__":
    print(policy.preview(attempts=3))
    response = policy.run(api.call)
    print(response.status_code, response.body)
