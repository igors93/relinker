from relinker import RetryPolicy, RetryResult


def test_return_result_configured_last_takes_precedence_over_fallback() -> None:
    policy = RetryPolicy().attempts(1).on(RuntimeError).fallback_value("safe").return_result()

    def task() -> str:
        raise RuntimeError("temporary")

    result = policy.run(task)

    assert isinstance(result, RetryResult)
    assert result.failed


def test_fallback_configured_last_takes_precedence_over_return_result() -> None:
    policy = RetryPolicy().attempts(1).on(RuntimeError).return_result().fallback_value("safe")

    def task() -> str:
        raise RuntimeError("temporary")

    assert policy.run(task) == "safe"
