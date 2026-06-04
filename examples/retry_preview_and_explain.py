from __future__ import annotations

from retryflow import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError, ConnectionError)
    .exponential_delay(base=1, maximum=10)
    .jitter(maximum=0.5)
)

if __name__ == "__main__":
    print(policy.explain())
    print()
    print(policy.preview(attempts=5))
