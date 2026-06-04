from __future__ import annotations

from relinker import RetryPolicy, TryAgain

attempts = 0


def task() -> str:
    global attempts
    attempts += 1
    if attempts < 3:
        raise TryAgain("not ready yet")
    return "ready"


policy = RetryPolicy().attempts(3).fixed_delay(0.1)


if __name__ == "__main__":
    print(policy.run(task))
