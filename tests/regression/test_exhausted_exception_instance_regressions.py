from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import TracebackType
from typing import Any

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy, RetryResult


class CustomExhaustedError(RuntimeError):
    pass


def _fail() -> None:
    raise RuntimeError("down")


def _capture_exhausted(policy: RetryPolicy[Any]) -> BaseException:
    try:
        policy.run(_fail)
    except BaseException as exc:
        return exc
    raise AssertionError("policy did not raise")


def _traceback_names(traceback: TracebackType | None) -> list[str]:
    names: list[str] = []
    current = traceback
    while current is not None:
        names.append(current.tb_frame.f_code.co_name)
        current = current.tb_next
    return names


def test_on_exhausted_raise_exception_instance_creates_independent_exceptions() -> None:
    shared = CustomExhaustedError("service unavailable")
    shared.status_code = 503  # type: ignore[attr-defined]
    policy = RetryPolicy().attempts(1).on_exhausted_raise(shared)

    exc1 = _capture_exhausted(policy)
    exc2 = _capture_exhausted(policy)

    assert exc1 is not shared
    assert exc2 is not shared
    assert exc1 is not exc2
    assert type(exc1) is type(shared)
    assert type(exc2) is type(shared)
    assert exc1.args == shared.args
    assert exc2.args == shared.args
    assert exc1.status_code == 503  # type: ignore[attr-defined]
    assert exc2.status_code == 503  # type: ignore[attr-defined]


def test_reused_policy_exhausted_exception_tracebacks_are_independent() -> None:
    shared = CustomExhaustedError("translated")
    policy = RetryPolicy().attempts(1).on_exhausted_raise(shared)

    def first_execution() -> BaseException:
        try:
            policy.run(_fail)
        except BaseException as exc:
            return exc
        raise AssertionError("policy did not raise")

    def second_execution() -> BaseException:
        try:
            policy.run(_fail)
        except BaseException as exc:
            return exc
        raise AssertionError("policy did not raise")

    exc1 = first_execution()
    tb1_names = _traceback_names(exc1.__traceback__)
    exc2 = second_execution()
    tb2_names = _traceback_names(exc2.__traceback__)

    assert exc1 is not exc2
    assert "first_execution" in tb1_names
    assert "second_execution" not in tb1_names
    assert "second_execution" in tb2_names
    assert "first_execution" not in tb2_names


def test_on_exhausted_raise_exception_instance_is_independent_across_threads() -> None:
    shared = CustomExhaustedError("threaded")
    policy = RetryPolicy().attempts(1).on_exhausted_raise(shared)

    with ThreadPoolExecutor(max_workers=2) as executor:
        exceptions = list(executor.map(lambda _: _capture_exhausted(policy), range(2)))

    assert len(exceptions) == 2
    assert exceptions[0] is not exceptions[1]
    assert all(isinstance(exc, CustomExhaustedError) for exc in exceptions)


def test_on_exhausted_raise_factory_is_called_once_per_exhaustion() -> None:
    calls: list[int] = []

    def factory(result: RetryResult[Any]) -> CustomExhaustedError:
        calls.append(result.attempt_count)
        return CustomExhaustedError("from factory")

    policy = RetryPolicy().attempts(1).on_exhausted_raise(factory)

    exc1 = _capture_exhausted(policy)
    exc2 = _capture_exhausted(policy)

    assert calls == [1, 1]
    assert exc1 is not exc2
    assert isinstance(exc1, CustomExhaustedError)
    assert isinstance(exc2, CustomExhaustedError)


def test_on_exhausted_raise_factory_returning_non_exception_fails_clearly() -> None:
    def factory(result: RetryResult[Any]) -> str:
        return f"attempts={result.attempt_count}"

    policy = RetryPolicy().attempts(1).on_exhausted_raise(factory)  # type: ignore[arg-type]

    with pytest.raises(
        InvalidRetryConfigError,
        match="exception factory must return a BaseException instance",
    ):
        policy.run(_fail)
