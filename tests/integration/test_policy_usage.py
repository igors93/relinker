from relinker import RetryPolicy


def test_policy_usage() -> None:
    policy = RetryPolicy().attempts(2).fixed_delay(0)

    @policy
    def task() -> str:
        return "ok"

    assert task() == "ok"
