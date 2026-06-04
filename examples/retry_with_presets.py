from __future__ import annotations

from retryflow import background_job, database, fast, network, patient


def show(name: str, policy: object) -> None:
    print(f"\n{name}")
    print(policy.explain())


if __name__ == "__main__":
    show("fast", fast())
    show("network", network())
    show("database", database())
    show("patient", patient())
    show("background_job", background_job())
