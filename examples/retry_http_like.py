"""
Example: HTTP-like retry policies using retryflow.http helpers.

No real HTTP calls are made. The fake client simulates connection errors
and status codes so you can see realistic retry behavior.
"""

from __future__ import annotations

from examples.fake_services import UnstableHTTPClient
from retryflow import RetryPolicy
from retryflow.http import retry_after_delay, retry_if_status, should_retry_http_status

RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


# --- Example 1: retry on connection errors ---


def example_retry_on_connection_error() -> None:
    print("=== Retry on connection error ===")
    client = UnstableHTTPClient(fail_times=2)

    def fetch() -> str:
        resp = client.get("https://api.example.com/data")
        return str(resp["body"])

    result = RetryPolicy().attempts(5).on(ConnectionError).fixed_delay(0).run(fetch)
    print(f"Result: {result}")
    print(f"Calls to client: {client.calls}")


# --- Example 2: retry on HTTP status codes ---


def example_retry_on_status_code() -> None:
    print("\n=== Retry on HTTP status code ===")

    # Simulate: first call returns 503, second returns 200
    responses = iter([{"status_code": 503}, {"status_code": 200, "body": "ok"}])

    def fetch() -> dict[str, object]:
        return next(responses)

    policy = (
        RetryPolicy()
        .attempts(5)
        .retry_if_result(retry_if_status(RETRYABLE_STATUSES))
        .fixed_delay(0)
        .return_result()
    )

    result = policy.run(fetch)
    print(f"Exhausted: {result.exhausted}")
    print(f"Attempts: {result.attempt_count}")
    last = result.last_value
    if last:
        print(f"Final status: {last.get('status_code')}")


# --- Example 3: should_retry_http_status for manual checks ---


def example_manual_status_check() -> None:
    print("\n=== Manual status check ===")
    statuses = [503, 429, 200]
    for code in statuses:
        should_retry = should_retry_http_status(code, RETRYABLE_STATUSES)
        print(f"  {code}: should_retry={should_retry}")


# --- Example 4: retry_after_delay as a fixed delay callback ---


def example_retry_after_delay() -> None:
    print("\n=== retry_after_delay as custom delay ===")
    policy = RetryPolicy().attempts(4).custom_delay(retry_after_delay(default=1.0, maximum=30.0))
    sim = policy.simulate(attempts=4)
    for a in sim.attempts:
        print(f"  Attempt {a.attempt_number}: delay={a.delay_before_next_attempt}s")


if __name__ == "__main__":
    example_retry_on_connection_error()
    example_retry_on_status_code()
    example_manual_status_check()
    example_retry_after_delay()
