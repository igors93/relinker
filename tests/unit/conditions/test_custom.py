from relinker.conditions.custom import CustomCondition


def test_custom_condition() -> None:
    condition = CustomCondition(lambda error, value: error is not None or value == "retry")

    assert condition.should_retry_exception(RuntimeError())
    assert condition.should_retry_result("retry")
    assert not condition.should_retry_result("ok")
