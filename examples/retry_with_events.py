from retryflow import RetryPolicy
from retryflow.event import RetryEvent


def log_event(event: RetryEvent) -> None:
    print(event)


policy = RetryPolicy().attempts(2).on_event("before_attempt", log_event)


@policy
def task() -> str:
    return "ok"


print(task())
