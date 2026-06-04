import pytest

from retryflow import RetryPolicy
from retryflow.exceptions import RetryExhaustedError


def test_sync_executor_return_result() -> None:
    result = RetryPolicy().attempts(1).return_result().run(lambda: "ok")

    assert result.succeeded
    assert result.value == "ok"


def test_sync_executor_does_not_swallow_keyboard_interrupt() -> None:
    def task() -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        RetryPolicy().attempts(3).return_result().run(task)


def test_sync_executor_marks_result_exhaustion_when_returning_result() -> None:
    result = (
        RetryPolicy()
        .attempts(2)
        .retry_if_result(lambda value: value is None)
        .return_result()
        .run(lambda: None)
    )

    assert result.failed
    assert result.exhausted
    assert result.exhausted_by_result
    assert result.value is None


def test_sync_executor_can_raise_on_result_exhaustion() -> None:
    policy = (
        RetryPolicy()
        .attempts(2)
        .retry_if_result(lambda value: value is None)
        .raise_on_result_exhausted()
    )

    with pytest.raises(RetryExhaustedError):
        policy.run(lambda: None)
