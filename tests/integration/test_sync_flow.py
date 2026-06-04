from retryflow import RetryPolicy


def test_sync_flow_retries_by_result() -> None:
    values = iter([None, "ok"])

    result = (
        RetryPolicy()
        .attempts(2)
        .retry_if_result(lambda value: value is None)
        .return_result()
        .run(lambda: next(values))
    )

    assert result.succeeded
    assert result.value == "ok"
    assert result.attempt_count == 2
