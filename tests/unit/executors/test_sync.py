from retryflow import RetryPolicy


def test_sync_executor_return_result() -> None:
    result = RetryPolicy().attempts(1).return_result().run(lambda: "ok")

    assert result.succeeded
    assert result.value == "ok"
