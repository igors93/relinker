from relinker.conditions.exception import ExceptionCondition
from relinker.conditions.result import ResultCondition


def test_any_condition_retries_when_either_condition_matches() -> None:
    condition = ExceptionCondition((TimeoutError,)) | ResultCondition(lambda value: value is None)

    assert condition.should_retry_exception(TimeoutError())
    assert condition.should_retry_result(None)
    assert not condition.should_retry_result("ok")


def test_all_condition_requires_both_conditions() -> None:
    condition = ResultCondition(lambda value: isinstance(value, str)) & ResultCondition(
        lambda value: value.startswith("retry")
    )

    assert condition.should_retry_result("retry-now")
    assert not condition.should_retry_result("ok")
