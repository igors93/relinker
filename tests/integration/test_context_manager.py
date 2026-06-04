from retryflow import RetryPolicy


def test_sync_context_manager_retries_exception() -> None:
    calls = {"count": 0}

    policy = RetryPolicy().attempts(3).on(RuntimeError)

    for attempt in policy.iter(name="test_block"):
        with attempt:
            calls["count"] += 1
            if calls["count"] < 2:
                raise RuntimeError("temporary")

    assert calls["count"] == 2


def test_sync_context_manager_retries_result() -> None:
    values = iter([None, "ok"])

    policy = RetryPolicy().attempts(3).retry_if_result(lambda value: value is None)

    for attempt in policy.iter(name="result_block"):
        with attempt:
            value = next(values)
            attempt.set_result(value)

    assert value == "ok"
