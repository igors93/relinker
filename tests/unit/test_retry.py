from retryflow import retry


def test_retry_eventually_succeeds() -> None:
    calls = {"count": 0}

    @retry(attempts=3)
    def task() -> str:
        calls["count"] += 1
        if calls["count"] < 2:
            raise RuntimeError("temporary failure")
        return "ok"

    assert task() == "ok"
    assert calls["count"] == 2
