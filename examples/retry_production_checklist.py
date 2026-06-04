from __future__ import annotations

from relinker import RetryPolicy

policies = {
    "api": RetryPolicy().attempts(5).on(TimeoutError).exponential_delay(base=1, maximum=30),
    "risky_worker": RetryPolicy().forever().on(Exception).no_delay(),
}


if __name__ == "__main__":
    for name, policy in policies.items():
        print(f"\n{name}")
        print(policy.explain())
        print()
        print(policy.doctor().describe())
