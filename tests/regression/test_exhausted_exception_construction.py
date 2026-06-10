"""Regression tests for Correction 7: robust exception construction in on_exhausted_raise.

The current code always does `ExceptionClass("Retry attempts were exhausted.")`,
which fails for no-arg exceptions, keyword-only constructors, and incompatible
signatures — replacing the exhaustion error with a spurious TypeError.

Tests verify:
- ValueError receives message (existing behavior preserved)
- no-arg exception works
- variadic *args exception works
- keyword-only exception fails early with InvalidRetryConfigError
- incompatible required-arg exception fails early with InvalidRetryConfigError
- __init__ that raises TypeError internally is not masked
- factory continues to work
- instance continues to work
- class not derived from BaseException is rejected early
- constructor TypeError is NOT silently swallowed
"""

from __future__ import annotations

import asyncio

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy

# ---------------------------------------------------------------------------
# Exception classes for testing
# ---------------------------------------------------------------------------


class NoArgError(Exception):
    def __init__(self) -> None:
        super().__init__("no-arg exception")


class MessageError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class VarArgError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class RequiredArgError(Exception):
    def __init__(self, code: int, detail: str) -> None:
        super().__init__(f"code={code} detail={detail}")


class KeywordOnlyError(Exception):
    def __init__(self, *, reason: str) -> None:
        super().__init__(reason)


class InternalTypeErrorError(Exception):
    """Constructor raises TypeError internally (not from wrong call signature)."""

    def __init__(self, message: str) -> None:
        raise TypeError("deliberate internal TypeError from constructor")


# ---------------------------------------------------------------------------
# Exception class — basic argument compatibility
# ---------------------------------------------------------------------------


class TestExceptionClassConstruction:
    def _make_policy(self, exc_cls: type) -> RetryPolicy:  # type: ignore[type-arg]
        return RetryPolicy().attempts(2).on(ValueError).on_exhausted_raise(exc_cls).for_testing()

    def _exhaust(self, policy: RetryPolicy) -> Exception:  # type: ignore[type-arg]
        with pytest.raises(Exception) as exc_info:
            policy.run(lambda: (_ for _ in ()).throw(ValueError("trigger")))
        return exc_info.value

    def test_value_error_receives_message(self) -> None:
        exc = self._exhaust(self._make_policy(ValueError))
        assert isinstance(exc, ValueError)
        assert "exhausted" in str(exc).lower()

    def test_no_arg_exception_works(self) -> None:
        exc = self._exhaust(self._make_policy(NoArgError))
        assert isinstance(exc, NoArgError)

    def test_message_exception_receives_message(self) -> None:
        exc = self._exhaust(self._make_policy(MessageError))
        assert isinstance(exc, MessageError)
        assert "exhausted" in str(exc).lower()

    def test_vararg_exception_receives_message(self) -> None:
        exc = self._exhaust(self._make_policy(VarArgError))
        assert isinstance(exc, VarArgError)

    def test_incompatible_required_arg_fails_early(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().on_exhausted_raise(RequiredArgError)

    def test_keyword_only_fails_early(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().on_exhausted_raise(KeywordOnlyError)

    def test_internal_constructor_type_error_not_masked(self) -> None:
        policy = self._make_policy(InternalTypeErrorError)
        with pytest.raises(TypeError, match="deliberate internal TypeError"):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("trigger")))

    def test_non_exception_class_rejected_early(self) -> None:
        class NotAnException:
            pass

        with pytest.raises((InvalidRetryConfigError, TypeError)):
            RetryPolicy().on_exhausted_raise(NotAnException)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Exception instance path
# ---------------------------------------------------------------------------


class TestExceptionInstanceConstruction:
    def test_instance_is_raised(self) -> None:
        policy = (
            RetryPolicy()
            .attempts(2)
            .on(ValueError)
            .on_exhausted_raise(MessageError("template"))
            .for_testing()
        )
        with pytest.raises(MessageError):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))

    def test_instance_with_custom_attrs(self) -> None:
        exc = MessageError("custom-msg")
        policy = RetryPolicy().attempts(2).on(ValueError).on_exhausted_raise(exc).for_testing()
        raised = None
        with pytest.raises(MessageError) as exc_info:
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
        raised = exc_info.value
        assert raised.message == "custom-msg"

    def test_new_instance_per_exhaustion(self) -> None:
        original = MessageError("template")
        policy = RetryPolicy().attempts(2).on(ValueError).on_exhausted_raise(original).for_testing()
        with pytest.raises(MessageError) as exc_info:
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
        raised = exc_info.value
        assert raised is not original


# ---------------------------------------------------------------------------
# Factory path
# ---------------------------------------------------------------------------


class TestExceptionFactory:
    def test_factory_receives_result_and_raises(self) -> None:
        from relinker.result import RetryResult

        captured: list[RetryResult] = []  # type: ignore[type-arg]

        def factory(result: RetryResult) -> BaseException:  # type: ignore[type-arg]
            captured.append(result)
            return MessageError("from factory")

        policy = RetryPolicy().attempts(2).on(ValueError).on_exhausted_raise(factory).for_testing()
        with pytest.raises(MessageError, match="from factory"):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
        assert captured
        assert captured[0].exhausted

    def test_factory_returning_non_exception_raises_config_error(self) -> None:
        def bad_factory(result: object) -> int:  # type: ignore[return-value]
            return 42  # type: ignore[return-value]

        policy = (
            RetryPolicy()
            .attempts(2)
            .on(ValueError)
            .on_exhausted_raise(bad_factory)  # type: ignore[arg-type]
            .for_testing()
        )
        with pytest.raises(InvalidRetryConfigError):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))

    def test_callable_object_factory_works(self) -> None:
        class Factory:
            def __call__(self, result: object) -> MessageError:
                return MessageError("callable factory")

        policy = (
            RetryPolicy().attempts(2).on(ValueError).on_exhausted_raise(Factory()).for_testing()
        )
        with pytest.raises(MessageError, match="callable factory"):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))


# ---------------------------------------------------------------------------
# Async parity
# ---------------------------------------------------------------------------


class TestAsyncParity:
    def test_no_arg_exception_async(self) -> None:
        policy = (
            RetryPolicy().attempts(2).on(ValueError).on_exhausted_raise(NoArgError).for_testing()
        )

        async def task() -> None:
            raise ValueError("x")

        with pytest.raises(NoArgError):
            asyncio.run(policy.run_async(task))

    def test_incompatible_exception_fails_early_same_as_sync(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().on_exhausted_raise(RequiredArgError)
