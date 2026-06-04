from retryflow.conditions.result import ResultCondition


def test_result_condition() -> None:
    condition = ResultCondition(lambda value: value is None)

    assert condition.should_retry_result(None)
    assert not condition.should_retry_result("ok")
