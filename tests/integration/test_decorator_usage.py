from relinker import retry


def test_decorator_usage() -> None:
    @retry(attempts=1)
    def task() -> str:
        return "ok"

    assert task() == "ok"
