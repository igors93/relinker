from __future__ import annotations

from retryflow import RetryPolicy

safe_policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(1)
risky_policy = RetryPolicy().forever().on(Exception).no_delay()


if __name__ == "__main__":
    print("Safe policy")
    print(safe_policy.doctor().describe())

    print("\nRisky policy")
    print(risky_policy.doctor().describe())
