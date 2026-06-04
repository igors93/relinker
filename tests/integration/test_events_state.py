from retryflow import RetryPolicy
from retryflow.event import RetryEvent


def test_events_include_state() -> None:
    events: list[RetryEvent] = []

    def collect(event: RetryEvent) -> None:
        events.append(event)

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(RuntimeError)
        .on_event("after_failure", collect)
        .on_event("before_sleep", collect)
    )

    calls = {"count": 0}

    def task() -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary")
        return "ok"

    assert policy.run(task) == "ok"
    assert events
    assert all(event.state is not None for event in events)
    assert events[0].state is not None
    assert events[0].state.attempt_number == 1
