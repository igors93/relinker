from typing import Any

from relinker import network


def test_network_preset_can_decorate_function_and_collect_stats() -> None:
    calls = {"count": 0}

    @network(RuntimeError)
    def task() -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary")
        return "ok"

    assert task() == "ok"

    stats: Any = task.retry_stats.to_dict()

    assert stats["calls"] == 1
    assert stats["successes"] == 1
    assert stats["total_attempts"] == 2


def test_preset_can_be_customized_like_normal_policy() -> None:
    policy = network(RuntimeError).attempts(2).fallback_value("fallback")

    def task() -> str:
        raise RuntimeError("temporary")

    assert policy.run(task) == "fallback"
