from __future__ import annotations

from examples.fake_services import FakeResponse, StatusSequence
from relinker import RetryPolicy, retry_if_status

api = StatusSequence(
    [
        FakeResponse(503, body="service unavailable"),
        FakeResponse(502, body="bad gateway"),
        FakeResponse(200, body="ok"),
    ]
)

policy = (
    RetryPolicy()
    .attempts(5)
    .retry_if_result(retry_if_status({429, 500, 502, 503, 504}))
    .fixed_delay(0.1)
)


if __name__ == "__main__":
    response = policy.run(api.call)
    print(response.status_code, response.body)
    print(f"calls: {api.calls}")
