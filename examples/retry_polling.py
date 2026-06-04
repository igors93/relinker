"""
Example: Polling patterns using TryAgain and retry_if_result.

Polling is a common use case where you repeatedly check a resource until
it reaches a desired state. RetryFlow supports it with TryAgain (signal
from inside the function) or retry_if_result (signal from the condition).
"""

from __future__ import annotations

from examples.fake_services import PollableJob
from retryflow import RetryPolicy, TryAgain
from retryflow.testing import no_sleep

# --- Example 1: poll with TryAgain ---


def example_poll_with_try_again() -> None:
    print("=== Poll with TryAgain ===")
    job = PollableJob(polls_needed=3)

    def check_status() -> str:
        status = job.status()
        if status != "completed":
            raise TryAgain(f"job is {status}, polling again")
        return status

    policy = RetryPolicy().attempts(10).fixed_delay(0)

    with no_sleep():
        result = policy.run(check_status)

    print(f"Final status: {result}")
    print(f"Polls made: {job.polls}")


# --- Example 2: poll with retry_if_result ---


def example_poll_with_result_condition() -> None:
    print("\n=== Poll with retry_if_result ===")
    job = PollableJob(polls_needed=4)

    policy = (
        RetryPolicy()
        .attempts(10)
        .retry_if_result(lambda status: status != "completed")
        .fixed_delay(0)
        .return_result()
    )

    with no_sleep():
        result = policy.run(job.status)

    print(f"Succeeded: {result.succeeded}")
    print(f"Final value: {result.value}")
    print(f"Polls: {result.attempt_count}")


# --- Example 3: poll with timeout ---


def example_poll_with_timeout() -> None:
    print("\n=== Poll with time limit ===")
    job = PollableJob(polls_needed=5)

    policy = (
        RetryPolicy()
        .attempts(3)  # limit attempts, not time
        .retry_if_result(lambda status: status != "completed")
        .fixed_delay(0)
        .fallback(lambda r: f"timed out after {r.attempt_count} polls")
    )

    with no_sleep():
        result = policy.run(job.status)

    print(f"Result: {result}")


if __name__ == "__main__":
    example_poll_with_try_again()
    example_poll_with_result_condition()
    example_poll_with_timeout()
