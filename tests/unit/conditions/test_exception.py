from relinker.conditions.exception import ExceptionCondition


def test_exception_condition() -> None:
    condition = ExceptionCondition((TimeoutError,))

    assert condition.should_retry_exception(TimeoutError())
    assert not condition.should_retry_exception(ValueError())
