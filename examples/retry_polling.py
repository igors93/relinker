from __future__ import annotations

from relinker import RetryPolicy

states = iter(["pending", "pending", "ready"])


def get_status() -> str:
    return next(states)


policy = RetryPolicy().attempts(5).retry_if_result(lambda value: value != "ready").fixed_delay(0.1)


if __name__ == "__main__":
    print(policy.run(get_status))
