from __future__ import annotations

from relinker import RetryPolicy
from relinker.result_conditions import (
    retry_if_empty,
    retry_if_false,
    retry_if_none,
    retry_if_value,
)


class NoLen:
    pass


class MatchesByParity:
    def __init__(self, value: int) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, MatchesByParity) and self.value % 2 == other.value % 2


def test_retry_if_none_only_matches_none() -> None:
    predicate = retry_if_none()

    assert predicate(None) is True
    assert predicate(False) is False
    assert predicate(0) is False
    assert predicate("") is False
    assert predicate([]) is False


def test_retry_if_false_only_matches_false() -> None:
    predicate = retry_if_false()

    assert predicate(False) is True
    assert predicate(None) is False
    assert predicate(0) is False
    assert predicate("") is False


def test_retry_if_empty_matches_empty_sized_values() -> None:
    predicate = retry_if_empty()

    assert predicate("") is True
    assert predicate([]) is True
    assert predicate({}) is True
    assert predicate(()) is True
    assert predicate("x") is False
    assert predicate([1]) is False
    assert predicate({"x": 1}) is False
    assert predicate(NoLen()) is False


def test_retry_if_value_uses_equality() -> None:
    assert retry_if_value("pending")("pending") is True
    assert retry_if_value("pending")("ready") is False
    assert retry_if_value(None)(None) is True
    assert retry_if_value(MatchesByParity(1))(MatchesByParity(3)) is True


def test_helpers_integrate_with_retry_if_result() -> None:
    values = iter([None, False, [], "ready"])
    policy = (
        RetryPolicy()
        .attempts(5)
        .retry_if_result(
            lambda value: (
                retry_if_none()(value) or retry_if_false()(value) or retry_if_empty()(value)
            )
        )
        .fixed_delay(0)
    )

    assert policy.run(lambda: next(values)) == "ready"


def test_retry_if_value_integrates_with_retry_if_result() -> None:
    values = iter(["pending", "pending", "ready"])
    policy = RetryPolicy().attempts(3).retry_if_result(retry_if_value("pending")).fixed_delay(0)

    assert policy.run(lambda: next(values)) == "ready"
