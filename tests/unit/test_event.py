from retryflow.event import RetryEvent


def test_event_creation() -> None:
    event = RetryEvent(name="before_attempt", attempt_number=1, function_name="task")

    assert event.name == "before_attempt"
    assert event.attempt_number == 1
    assert event.function_name == "task"
