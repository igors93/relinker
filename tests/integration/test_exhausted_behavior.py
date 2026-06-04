import pytest

from retryflow import RetryPolicy


class CustomExhaustedError(RuntimeError):
    pass


def test_fallback_value_for_exception_exhaustion() -> None:
    policy = RetryPolicy().attempts(2).on(RuntimeError).fallback_value("fallback")

    def task() -> str:
        raise RuntimeError("temporary")

    assert policy.run(task) == "fallback"


def test_fallback_callback_receives_result() -> None:
    def fallback(result):
        return f"attempts={result.attempt_count}"

    policy = RetryPolicy().attempts(2).on(RuntimeError).fallback(fallback)

    def task() -> str:
        raise RuntimeError("temporary")

    assert policy.run(task) == "attempts=2"


def test_custom_exception_on_exhaustion() -> None:
    policy = RetryPolicy().attempts(2).on(RuntimeError).on_exhausted_raise(CustomExhaustedError)

    def task() -> str:
        raise RuntimeError("temporary")

    with pytest.raises(CustomExhaustedError):
        policy.run(task)


def test_custom_exception_factory_on_exhaustion() -> None:
    def make_error(result):
        return CustomExhaustedError(f"failed after {result.attempt_count}")

    policy = RetryPolicy().attempts(2).on(RuntimeError).on_exhausted_raise(make_error)

    def task() -> str:
        raise RuntimeError("temporary")

    with pytest.raises(CustomExhaustedError, match="failed after 2"):
        policy.run(task)
