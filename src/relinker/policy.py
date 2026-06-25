"""
Retry policy builder.

RetryPolicy is the main public object in Relinker. It is an immutable builder:
every configuration method returns a new policy so it can be shared and reused
safely without side effects.

Implementation details are kept in the internal/ modules so this file remains a
readable public facade.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any, Generic, Literal, overload

from relinker.budget import RetryBudget
from relinker.conditions.base import RetryCondition
from relinker.conditions.composite import AllCondition, AnyCondition
from relinker.conditions.custom import CustomCondition
from relinker.conditions.exception import ExceptionCondition
from relinker.conditions.result import ResultCondition
from relinker.context import AsyncRetryBlockIterator, RetryBlockIterator
from relinker.delays.base import DelayStrategy
from relinker.delays.chain import ChainDelay
from relinker.delays.composite import AdditiveDelay
from relinker.delays.custom import CustomDelay
from relinker.delays.exponential import ExponentialDelay
from relinker.delays.fixed import FixedDelay
from relinker.delays.linear import LinearDelay
from relinker.delays.random_delay import RandomDelay
from relinker.delays.random_exponential import RandomExponentialDelay
from relinker.delays.stateful import StatefulCustomDelay
from relinker.diagnostics import (
    PolicyHealthReport,
    PolicyWarning,
    RetryLoadEstimate,
    RetrySimulation,
)
from relinker.event import (
    EventFailureMode,
    EventHandler,
    EventHandlerRegistration,
    EventName,
    RetryEvent,
    VALID_EVENT_NAMES,
)
from relinker.exceptions import InvalidRetryConfigError
from relinker.executors.async_ import execute_async
from relinker.executors.sync import execute_sync
from relinker.internal.callables import (
    ensure_callable,
    ensure_retryable_callable,
    ensure_sync_retryable_callable,
    ensure_sync_sleeper,
    instantiate_exception_class,
    is_async_callable,
    validate_exception_class,
)
from relinker.internal.sleep import async_sleep as default_async_sleep
from relinker.internal.sleep import sleep as default_sleep
from relinker.result import RetryResult
from relinker.state import RetryState
from relinker.stop.attempts import StopAfterAttempt
from relinker.stop.base import StopStrategy
from relinker.stop.forever import StopForever
from relinker.stop.max_time import StopAfterDelay
from relinker.typing import P, RetryWrappedFunction, T

ResultExhaustedBehavior = Literal["return_last", "raise"]
ExhaustedCallback = Callable[[RetryResult[Any]], Any]
ExceptionFactory = Callable[[RetryResult[Any]], BaseException]
StatefulDelayCallback = Callable[[RetryState], float]
EventHandlerEntry = EventHandlerRegistration | tuple[EventName, EventHandler]
_EVENT_FAILURE_LOGGER_NAME = "relinker.events"


def _no_sleep(_: float) -> None:
    """No-op sync sleep used by for_testing()."""


async def _no_sleep_async(_: float) -> None:
    """No-op async sleep used by for_testing()."""


def _copy_exception_instance(exception: BaseException) -> BaseException:
    """Create a fresh exception instance from a configured exception object."""
    try:
        copied = copy.copy(exception)
    except Exception:  # noqa: BLE001
        copied = type(exception)(*exception.args)

    if copied is exception:
        copied = type(exception)(*exception.args)
        if hasattr(exception, "__dict__"):
            copied.__dict__.update(exception.__dict__)

    copied.__traceback__ = None
    copied.__cause__ = None
    copied.__context__ = None
    copied.__suppress_context__ = getattr(exception, "__suppress_context__", False)
    return copied


def _flatten_any_conditions(conditions: tuple[RetryCondition, ...]) -> tuple[RetryCondition, ...]:
    flattened: list[RetryCondition] = []
    for condition in conditions:
        if isinstance(condition, AnyCondition):
            flattened.extend(condition.conditions)
        else:
            flattened.append(condition)
    return tuple(flattened)


def _flatten_all_conditions(conditions: tuple[RetryCondition, ...]) -> tuple[RetryCondition, ...]:
    flattened: list[RetryCondition] = []
    for condition in conditions:
        if isinstance(condition, AllCondition):
            flattened.extend(condition.conditions)
        else:
            flattened.append(condition)
    return tuple(flattened)


def _flatten_any_stop_strategies(strategies: tuple[StopStrategy, ...]) -> tuple[StopStrategy, ...]:
    from relinker.stop.composite import AnyStopStrategy

    flattened: list[StopStrategy] = []
    for strategy in strategies:
        if isinstance(strategy, AnyStopStrategy):
            flattened.extend(strategy.strategies)
        else:
            flattened.append(strategy)
    return tuple(flattened)


def _flatten_all_stop_strategies(strategies: tuple[StopStrategy, ...]) -> tuple[StopStrategy, ...]:
    from relinker.stop.composite import AllStopStrategy

    flattened: list[StopStrategy] = []
    for strategy in strategies:
        if isinstance(strategy, AllStopStrategy):
            flattened.extend(strategy.strategies)
        else:
            flattened.append(strategy)
    return tuple(flattened)


def _report_isolated_event_failure(event: RetryEvent, error: Exception) -> None:
    with suppress(Exception):
        logging.getLogger(_EVENT_FAILURE_LOGGER_NAME).warning(
            (
                "Isolated event handler failed event=%s attempt=%d "
                "function=%s policy=%s error_type=%s"
            ),
            event.name,
            event.attempt_number,
            event.function_name,
            event.policy_name or "",
            error.__class__.__name__,
        )


@dataclass(frozen=True, slots=True)
class RetryPolicy(Generic[T]):
    """
    Immutable retry policy builder.

    The policy stores configuration only. Executors perform the actual execution.
    Every builder method returns a new policy; the original is never modified.
    """

    stop_strategy: StopStrategy = StopAfterAttempt(3)
    delay_strategy: DelayStrategy = FixedDelay(0)
    condition: RetryCondition = ExceptionCondition((Exception,))
    should_raise_last: bool = True
    should_return_result: bool = False
    result_exhausted_behavior: ResultExhaustedBehavior = "return_last"
    exhausted_callback: ExhaustedCallback | None = None
    exhausted_exception_factory: ExceptionFactory | None = None
    event_handlers: tuple[EventHandlerEntry, ...] = ()
    sleep: Callable[[float], None] = default_sleep
    async_sleep: Callable[[float], Awaitable[None]] = default_async_sleep
    history_limit: int | None = 1000
    retry_budget: RetryBudget | None = None
    retry_budget_key: str | None = None
    name: str | None = None
    testing_mode: bool = False

    def __post_init__(self) -> None:
        if self.name is not None and (not isinstance(self.name, str) or not self.name.strip()):
            raise InvalidRetryConfigError("policy name must be a non-empty string")
        if self.history_limit is not None:
            from relinker.internal.validation import ensure_positive_int

            ensure_positive_int("history_limit", self.history_limit)
        if self.retry_budget is None and self.retry_budget_key is not None:
            raise InvalidRetryConfigError("retry_budget_key requires a RetryBudget")
        if self.retry_budget is not None:
            if not isinstance(self.retry_budget, RetryBudget):
                raise InvalidRetryConfigError("retry_budget must be a RetryBudget")
            if self.retry_budget_key is None or not self.retry_budget_key.strip():
                raise InvalidRetryConfigError("retry budget key must be a non-empty string")
        explicit_exhaustion_behaviors = sum(
            (
                self.should_return_result,
                self.exhausted_callback is not None,
                self.exhausted_exception_factory is not None,
            )
        )
        if explicit_exhaustion_behaviors > 1 or (
            self.should_raise_last and explicit_exhaustion_behaviors > 0
        ):
            raise InvalidRetryConfigError("exhaustion behaviors are mutually exclusive")
        # Validate sleeper contracts at construction time.
        # The default sleepers (_no_sleep, default_sleep) are always valid, so we skip
        # validation only for the sentinel no-ops to avoid import-time overhead.
        if self.sleep is not _no_sleep and self.sleep is not default_sleep:
            ensure_sync_sleeper(self.sleep)
        if self.async_sleep is not _no_sleep_async and self.async_sleep is not default_async_sleep:
            ensure_callable("async_sleep", self.async_sleep)

    def named(self, name: str) -> RetryPolicy[T]:
        """Return a new policy with a human-readable optional name."""
        if not isinstance(name, str) or not name.strip():
            raise InvalidRetryConfigError("policy name must be a non-empty string")
        return replace(self, name=name)

    # ------------------------------------------------------------------ stop

    def attempts(self, maximum: int) -> RetryPolicy[T]:
        """Return a new policy that stops after a maximum number of attempts."""
        return replace(self, stop_strategy=StopAfterAttempt(maximum))

    def forever(self) -> RetryPolicy[T]:
        """Return a new policy that never stops by attempt count."""
        return replace(self, stop_strategy=StopForever())

    def max_time(self, seconds: float) -> RetryPolicy[T]:
        """Return a new policy that stops after the given elapsed time.

        This is a retry-loop time budget, not a hard timeout for a function call.
        The budget is checked between attempts and before sleeping.
        """
        return replace(self, stop_strategy=StopAfterDelay(seconds))

    def stop_when(self, strategy: StopStrategy) -> RetryPolicy[T]:
        """Return a new policy using a custom stop strategy."""
        return replace(self, stop_strategy=strategy)

    def or_stop_after_attempts(self, maximum: int) -> RetryPolicy[T]:
        """Return a new policy that stops on current strategy OR attempt limit."""
        from relinker.stop.composite import AnyStopStrategy

        return replace(
            self,
            stop_strategy=AnyStopStrategy(
                _flatten_any_stop_strategies((self.stop_strategy, StopAfterAttempt(maximum)))
            ),
        )

    def or_stop_after_time(self, seconds: float) -> RetryPolicy[T]:
        """Return a new policy that stops on current strategy OR elapsed time."""
        from relinker.stop.composite import AnyStopStrategy

        return replace(
            self,
            stop_strategy=AnyStopStrategy(
                _flatten_any_stop_strategies((self.stop_strategy, StopAfterDelay(seconds)))
            ),
        )

    def and_stop_after_attempts(self, maximum: int) -> RetryPolicy[T]:
        """Return a new policy that stops only when both strategies stop."""
        from relinker.stop.composite import AllStopStrategy

        return replace(
            self,
            stop_strategy=AllStopStrategy(
                _flatten_all_stop_strategies((self.stop_strategy, StopAfterAttempt(maximum)))
            ),
        )

    def and_stop_after_time(self, seconds: float) -> RetryPolicy[T]:
        """Return a new policy that stops only when both strategies stop."""
        from relinker.stop.composite import AllStopStrategy

        return replace(
            self,
            stop_strategy=AllStopStrategy(
                _flatten_all_stop_strategies((self.stop_strategy, StopAfterDelay(seconds)))
            ),
        )

    # ----------------------------------------------------------- conditions

    def on(self, *exception_types: type[BaseException]) -> RetryPolicy[T]:
        """Return a new policy that retries on the given exception types."""
        types = exception_types or (Exception,)
        for exception_type in types:
            if not isinstance(exception_type, type):
                raise InvalidRetryConfigError(
                    f"exception types must be classes, got {type(exception_type).__name__}"
                )
            if not issubclass(exception_type, Exception):
                raise InvalidRetryConfigError(
                    f"{exception_type.__name__} is a BaseException subclass"
                    " that the executor never catches"
                )
        return replace(self, condition=ExceptionCondition(types))

    def retry_if_result(self, predicate: Callable[[Any], bool]) -> RetryPolicy[T]:
        """Return a new policy that retries when a result predicate is true."""
        ensure_callable("predicate", predicate)
        return replace(self, condition=ResultCondition(predicate))

    def retry_if(self, callback: Callable[[BaseException | None, Any], bool]) -> RetryPolicy[T]:
        """
        Return a new policy with a fully custom retry condition.

        The callback receives ``(error, value)``. For exception decisions,
        error is the raised exception and value is None. For result decisions,
        error is None and value is the returned value; value may be None when
        the wrapped function returned None.
        """
        ensure_callable("callback", callback)
        return replace(self, condition=CustomCondition(callback))

    def any_condition(self, *conditions: RetryCondition) -> RetryPolicy[T]:
        """Return a new policy that retries when any condition matches."""
        return replace(self, condition=AnyCondition(_flatten_any_conditions(conditions)))

    def all_conditions(self, *conditions: RetryCondition) -> RetryPolicy[T]:
        """Return a new policy that retries only when all conditions match."""
        return replace(self, condition=AllCondition(_flatten_all_conditions(conditions)))

    def or_on(self, *exception_types: type[BaseException]) -> RetryPolicy[T]:
        """Return a new policy that OR-combines current condition with exception retry."""
        return replace(
            self,
            condition=AnyCondition(
                _flatten_any_conditions((self.condition, ExceptionCondition(exception_types)))
            ),
        )

    def or_retry_if_result(self, predicate: Callable[[Any], bool]) -> RetryPolicy[T]:
        """Return a new policy that OR-combines current condition with result retry."""
        ensure_callable("predicate", predicate)
        return replace(
            self,
            condition=AnyCondition(
                _flatten_any_conditions((self.condition, ResultCondition(predicate)))
            ),
        )

    # --------------------------------------------------------------- delays

    def fixed_delay(self, seconds: float) -> RetryPolicy[T]:
        """Return a new policy with a fixed delay strategy."""
        return replace(self, delay_strategy=FixedDelay(seconds))

    def no_delay(self) -> RetryPolicy[T]:
        """Return a new policy with zero delay."""
        return self.fixed_delay(0)

    def linear_delay(
        self,
        *,
        start: float = 0.0,
        step: float = 1.0,
        maximum: float | None = None,
    ) -> RetryPolicy[T]:
        """Return a new policy with linear delay."""
        return replace(self, delay_strategy=LinearDelay(start=start, step=step, maximum=maximum))

    def chain_delay(self, delays: list[float] | tuple[float, ...]) -> RetryPolicy[T]:
        """
        Return a new policy with a predefined delay sequence.

        When attempts exceed the sequence length, the last delay is reused.
        """
        return replace(self, delay_strategy=ChainDelay(tuple(delays)))

    def exponential_delay(
        self,
        *,
        base: float = 1.0,
        factor: float = 2.0,
        maximum: float | None = None,
    ) -> RetryPolicy[T]:
        """Return a new policy with exponential delay."""
        return replace(
            self,
            delay_strategy=ExponentialDelay(base=base, factor=factor, maximum=maximum),
        )

    def random_exponential_delay(
        self,
        *,
        base: float = 1.0,
        factor: float = 2.0,
        minimum: float = 0.0,
        maximum: float | None = None,
        seed: int | None = None,
    ) -> RetryPolicy[T]:
        """Return a new policy with random exponential delay."""
        return replace(
            self,
            delay_strategy=RandomExponentialDelay(
                base=base,
                factor=factor,
                minimum=minimum,
                maximum=maximum,
                seed=seed,
            ),
        )

    def random_delay(
        self,
        *,
        minimum: float = 0.0,
        maximum: float = 1.0,
        seed: int | None = None,
    ) -> RetryPolicy[T]:
        """Return a new policy with random delay."""
        return replace(
            self,
            delay_strategy=RandomDelay(minimum=minimum, maximum=maximum, seed=seed),
        )

    def jitter(
        self,
        *,
        minimum: float = 0.0,
        maximum: float = 1.0,
        seed: int | None = None,
    ) -> RetryPolicy[T]:
        """
        Return a new policy that adds random jitter to the current delay.

        Example:
            RetryPolicy().exponential_delay(base=1).jitter(maximum=0.5)
        """
        jitter_delay = RandomDelay(minimum=minimum, maximum=maximum, seed=seed)
        return replace(
            self,
            delay_strategy=AdditiveDelay((self.delay_strategy, jitter_delay)),
        )

    def add_delay(self, strategy: DelayStrategy) -> RetryPolicy[T]:
        """Return a new policy that adds a delay strategy to the current strategy."""
        return replace(
            self,
            delay_strategy=AdditiveDelay((self.delay_strategy, strategy)),
        )

    def custom_delay(self, callback: Callable[[int], float]) -> RetryPolicy[T]:
        """Return a new policy with a custom delay callback (receives attempt number)."""
        ensure_callable("callback", callback)
        return replace(self, delay_strategy=CustomDelay(callback))

    def stateful_delay(self, callback: StatefulDelayCallback) -> RetryPolicy[T]:
        """
        Return a new policy with a state-aware delay callback.

        The callback receives a RetryState snapshot before each sleep and must
        return a non-negative float (seconds). This enables delays that adapt
        based on the last error, last value, elapsed time, or response headers.
        """
        ensure_callable("callback", callback)
        return replace(self, delay_strategy=StatefulCustomDelay(callback))

    # -------------------------------------------------- exhausted behavior

    def _replace_exhaustion(
        self,
        *,
        should_raise_last: bool = False,
        should_return_result: bool = False,
        exhausted_callback: ExhaustedCallback | None = None,
        exhausted_exception_factory: ExceptionFactory | None = None,
    ) -> RetryPolicy[T]:
        """Return a new policy with one mutually exclusive exhaustion behavior."""
        return replace(
            self,
            should_raise_last=should_raise_last,
            should_return_result=should_return_result,
            exhausted_callback=exhausted_callback,
            exhausted_exception_factory=exhausted_exception_factory,
        )

    def raise_last(self) -> RetryPolicy[T]:
        """Return a new policy that re-raises the last original exception."""
        return self._replace_exhaustion(
            should_raise_last=True,
        )

    def return_result(self) -> RetryPolicy[T]:
        """Return a new policy that returns RetryResult instead of raising."""
        return self._replace_exhaustion(
            should_return_result=True,
        )

    def raise_on_result_exhausted(self) -> RetryPolicy[T]:
        """
        Return a new policy that raises RetryExhaustedError when result retry is exhausted.

        The default behavior returns the last value silently. This option makes
        exhaustion explicit.
        """
        return replace(self, result_exhausted_behavior="raise")

    def return_last_on_result_exhausted(self) -> RetryPolicy[T]:
        """Return a new policy that returns the last value when result retry is exhausted."""
        return replace(self, result_exhausted_behavior="return_last")

    def on_exhausted_return(self, callback: ExhaustedCallback) -> RetryPolicy[T]:
        """
        Return a new policy that calls a fallback when retry attempts are exhausted.

        The callback receives RetryResult and its return value becomes the final
        return value.
        """
        ensure_callable("callback", callback)
        return self._replace_exhaustion(
            exhausted_callback=callback,
        )

    def on_exhausted_return_value(self, value: Any) -> RetryPolicy[T]:
        """Return a new policy that returns a fixed value when retries are exhausted."""

        def callback(result: RetryResult[Any]) -> Any:
            return value

        return self.on_exhausted_return(callback)

    def fallback(self, callback: ExhaustedCallback) -> RetryPolicy[T]:
        """Alias for on_exhausted_return with a shorter name."""
        return self.on_exhausted_return(callback)

    def fallback_value(self, value: Any) -> RetryPolicy[T]:
        """Alias for on_exhausted_return_value with a shorter name."""
        return self.on_exhausted_return_value(value)

    def on_exhausted_raise(
        self,
        exception: BaseException | type[BaseException] | ExceptionFactory,
    ) -> RetryPolicy[T]:
        """
        Return a new policy that raises a custom exception when retries are exhausted.

        Accepted values:
            - an exception instance
            - an exception class
            - a factory that receives RetryResult and returns an exception
        """
        resolved_factory: ExceptionFactory

        if isinstance(exception, type) and issubclass(exception, BaseException):
            _MESSAGE = "Retry attempts were exhausted."
            # Validate early: check signature without calling the constructor.
            validate_exception_class(exception, _MESSAGE)

            def make_from_class(result: RetryResult[Any]) -> BaseException:
                return instantiate_exception_class(exception, _MESSAGE)

            resolved_factory = make_from_class
        elif isinstance(exception, type):
            # Class that is not a BaseException subclass — reject early
            raise InvalidRetryConfigError(
                f"{exception.__name__} is not a BaseException subclass; "
                "pass an exception class, an exception instance, or a factory callable"
            )
        elif isinstance(exception, BaseException):

            def make_from_instance(result: RetryResult[Any]) -> BaseException:
                return _copy_exception_instance(exception)

            resolved_factory = make_from_instance
        elif callable(exception):
            resolved_factory = exception
        else:
            raise InvalidRetryConfigError("exception must be an exception, class, or factory")

        return self._replace_exhaustion(
            exhausted_exception_factory=resolved_factory,
        )

    # --------------------------------------------------- history / budget

    def keep_history(self, maximum: int | None) -> RetryPolicy[T]:
        """Return a policy retaining at most ``maximum`` attempt records."""
        if maximum is not None:
            from relinker.internal.validation import ensure_positive_int

            ensure_positive_int("maximum", maximum)
        return replace(self, history_limit=maximum)

    def with_retry_budget(
        self,
        budget: RetryBudget,
        *,
        key: str,
    ) -> RetryPolicy[T]:
        """Return a policy sharing retry capacity through ``budget`` and ``key``.

        Policy configuration remains immutable. The budget is an explicitly
        shared runtime collaborator, so derived policies using the same object
        and key intentionally share capacity.
        """
        if not isinstance(budget, RetryBudget):
            raise InvalidRetryConfigError("budget must be a RetryBudget")
        if not isinstance(key, str) or not key.strip():
            raise InvalidRetryConfigError("retry budget key must be a non-empty string")
        return replace(self, retry_budget=budget, retry_budget_key=key)

    def without_retry_budget(self) -> RetryPolicy[T]:
        """Return a policy with shared retry budgeting disabled."""
        return replace(self, retry_budget=None, retry_budget_key=None)

    # -------------------------------------------------- sleep / test hooks

    def with_sleep(
        self,
        sleep: Callable[[float], None],
        async_sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> RetryPolicy[T]:
        """
        Return a new policy with custom sleep functions.

        Useful for tests (with no_sleep()) and advanced integrations.
        """
        ensure_sync_sleeper(sleep)
        if async_sleep is not None:
            ensure_callable("async_sleep", async_sleep)
        resolved_async_sleep = async_sleep
        if resolved_async_sleep is None:
            resolved_async_sleep = default_async_sleep if self.testing_mode else self.async_sleep
        return replace(
            self,
            sleep=sleep,
            async_sleep=resolved_async_sleep,
            testing_mode=False,
        )

    def for_testing(self) -> RetryPolicy[T]:
        """Return a copy of this policy with sync and async sleep replaced by no-ops.

        All other settings (attempts, conditions, delays, event handlers, etc.) are
        preserved. This makes tests run without real delays.

        Note: ``max_time`` and retry-budget windows are not virtually advanced.
        They use real wall-clock time and will behave as if no time passes between
        retries.
        """
        return replace(
            self.with_sleep(_no_sleep, _no_sleep_async),
            testing_mode=True,
        )

    # ------------------------------------------------------------ events

    def on_event(
        self,
        name: EventName,
        handler: EventHandler,
        *,
        failure_mode: EventFailureMode = "propagate",
    ) -> RetryPolicy[T]:
        """Return a new policy with an additional event handler."""
        if name not in VALID_EVENT_NAMES:
            accepted = ", ".join(sorted(VALID_EVENT_NAMES))
            raise InvalidRetryConfigError(
                f"unknown event name {name!r}; expected one of: {accepted}"
            )
        ensure_callable("handler", handler)
        if is_async_callable(handler):
            raise InvalidRetryConfigError(
                "Async event handlers are not supported; use a synchronous handler."
            )
        if failure_mode not in ("propagate", "isolate"):
            raise InvalidRetryConfigError("failure_mode must be 'propagate' or 'isolate'")
        registration = EventHandlerRegistration(name, handler, failure_mode)
        return replace(self, event_handlers=(*self.event_handlers, registration))

    def on_before_attempt(self, handler: EventHandler) -> RetryPolicy[T]:
        """Return a new policy that calls handler before each attempt."""
        return self.on_event("before_attempt", handler)

    def on_success(self, handler: EventHandler) -> RetryPolicy[T]:
        """Return a new policy that calls handler after an accepted successful result."""
        return self.on_event("after_success", handler)

    def on_failure(self, handler: EventHandler) -> RetryPolicy[T]:
        """Return a new policy that calls handler after a failed attempt."""
        return self.on_event("after_failure", handler)

    def on_retry(self, handler: EventHandler) -> RetryPolicy[T]:
        """Return a new policy that calls handler before sleeping for a retry."""
        return self.on_event("before_sleep", handler)

    def on_giveup(self, handler: EventHandler) -> RetryPolicy[T]:
        """Return a new policy that calls handler when Relinker gives up."""
        return self.on_event("after_giveup", handler)

    def debug(self, *, include_error_message: bool = False) -> RetryPolicy[T]:
        """
        Return a new policy with simple console debug events enabled.

        Error messages are excluded by default because they may contain secrets,
        tokens, URLs, or payload fragments. Set ``include_error_message=True``
        when you explicitly need the message text and have verified it is safe.
        """

        def print_event(event: RetryEvent) -> None:
            if event.name == "before_attempt":
                print(f"[relinker] attempt {event.attempt_number} started: {event.function_name}")
            elif event.name == "after_failure" and event.error is not None:
                error_part = event.error.__class__.__name__
                if include_error_message:
                    try:
                        error_part += f": {event.error}"
                    except Exception:  # noqa: BLE001
                        error_part += ": <error rendering message>"
                message = f"[relinker] attempt {event.attempt_number} failed: {error_part}"
                print(message)
            elif event.name == "before_sleep" and event.delay is not None:
                print(f"[relinker] sleeping {event.delay:.4f}s before next attempt")
            elif event.name == "after_success":
                print(f"[relinker] attempt {event.attempt_number} succeeded")
            elif event.name == "after_giveup":
                print(f"[relinker] giving up after attempt {event.attempt_number}")

        policy = self
        for event_name in (
            "before_attempt",
            "after_failure",
            "before_sleep",
            "after_success",
            "after_giveup",
        ):
            policy = policy.on_event(event_name, print_event, failure_mode="isolate")
        return policy

    def with_logging(
        self,
        *,
        level: int = logging.WARNING,
        logger: logging.Logger | None = None,
        include_error_message: bool = False,
    ) -> RetryPolicy[T]:
        """
        Return a new policy that logs retry activity using the standard library.

        Logs before each sleep and after giving up. Successful first attempts are
        not logged to avoid noise.

        Error messages are excluded by default because they may contain secrets,
        tokens, URLs, or payload fragments. Set ``include_error_message=True``
        when you explicitly need the message text and have verified it is safe to log.
        """
        from relinker.internal.policy_logging import make_logging_handler

        _logger = logger if logger is not None else logging.getLogger("relinker")
        handler = make_logging_handler(level, _logger, include_error_message=include_error_message)
        policy: RetryPolicy[T] = self
        for event_name in ("before_sleep", "after_giveup"):
            policy = policy.on_event(event_name, handler, failure_mode="isolate")
        return policy

    def with_structured_logging(
        self,
        *,
        level: int = logging.INFO,
        logger: logging.Logger | None = None,
        include_error_message: bool = False,
    ) -> RetryPolicy[T]:
        """
        Return a new policy that logs retry events as compact JSON strings.

        Error messages are excluded by default because they may contain sensitive
        user data, tokens, URLs, or payload fragments.
        """
        from relinker.internal.policy_logging import make_structured_logging_handler

        _logger = logger if logger is not None else logging.getLogger("relinker")
        handler = make_structured_logging_handler(
            level,
            _logger,
            include_error_message=include_error_message,
        )
        policy: RetryPolicy[T] = self
        for event_name in ("before_sleep", "after_giveup"):
            policy = policy.on_event(event_name, handler, failure_mode="isolate")
        return policy

    def _has_handler(self, name: EventName) -> bool:
        """Return True when at least one handler is registered for the given event name."""
        for registration in self.event_handlers:
            if isinstance(registration, EventHandlerRegistration):
                if registration.name == name:
                    return True
            else:
                reg_name, _ = registration
                if reg_name == name:
                    return True
        return False

    def emit(self, event: RetryEvent) -> None:
        """Emit an event to all matching handlers."""
        if self.name is not None and event.policy_name is None:
            state = event.state
            if state is not None and state.policy_name is None:
                state = replace(state, policy_name=self.name)
            event = replace(event, policy_name=self.name, state=state)
        for registration in self.event_handlers:
            if isinstance(registration, EventHandlerRegistration):
                name = registration.name
                handler = registration.handler
                failure_mode = registration.failure_mode
            else:
                name, handler = registration
                failure_mode = "propagate"
            if name == event.name:
                try:
                    handler(event)
                except Exception as error:
                    if failure_mode == "isolate":
                        _report_isolated_event_failure(event, error)
                        continue
                    raise

    # --------------------------------------------------------- diagnostics

    def warnings(self) -> tuple[PolicyWarning, ...]:
        """
        Return non-blocking advisory warnings about this policy.

        Relinker does not block application-level choices. Warnings help users
        notice risky configurations before production.
        """
        from relinker.internal.policy_diagnostics import compute_warnings

        return compute_warnings(self)

    def doctor(self) -> PolicyHealthReport:
        """Return a human-friendly health report for this policy."""
        from relinker.internal.policy_diagnostics import doctor_policy

        return doctor_policy(self)

    def simulate(self, attempts: int = 5) -> RetrySimulation:
        """
        Simulate the delay timeline without executing user code.

        The simulation is advisory and deterministic for built-in delays.
        Policies with CustomDelay or StatefulCustomDelay callbacks are not supported
        because simulating them would execute user code.
        """
        from relinker.internal.policy_simulation import simulate_policy

        return simulate_policy(self, attempts)

    def explain(self) -> str:
        """Return a human-readable explanation of this policy and any warnings."""
        from relinker.internal.policy_simulation import explain_policy

        return explain_policy(self)

    def timeline(self, attempts: int = 5) -> str:
        """
        Return an estimated delay timeline as a readable string.

        This is a shortcut for simulate(attempts).describe().
        """
        return self.simulate(attempts=attempts).describe()

    def estimate_load(self, *, concurrent_executions: int) -> RetryLoadEstimate:
        """Return a worst-case call estimate for concurrent executions."""
        from relinker.internal.policy_simulation import estimate_policy_load

        return estimate_policy_load(self, concurrent_executions)

    def preview(
        self,
        attempts: int = 5,
        *,
        concurrent_executions: int | None = None,
    ) -> str:
        """Return a concise preview of retry timing and policy warnings."""
        from relinker.internal.policy_simulation import preview_policy

        return preview_policy(self, attempts, concurrent_executions)

    def to_dict(self) -> dict[str, object]:
        """Return a structured representation of this policy configuration."""
        from relinker.internal.policy_serialization import policy_to_dict

        return policy_to_dict(self)

    # -------------------------------------------------- iteration / blocks

    def iter(self, *, name: str = "retry_block") -> RetryBlockIterator:
        """Return a sync retry-block iterator."""
        return RetryBlockIterator(self, name=name)

    def async_iter(self, *, name: str = "retry_block") -> AsyncRetryBlockIterator:
        """Return an async retry-block iterator."""
        return AsyncRetryBlockIterator(self, name=name)

    def __iter__(self) -> RetryBlockIterator:
        """Allow `for attempt in policy:` syntax for retry blocks."""
        return self.iter()

    def __aiter__(self) -> AsyncRetryBlockIterator:
        """Allow `async for attempt in policy:` syntax for retry blocks."""
        return self.async_iter()

    # ------------------------------------------------- execution shortcuts

    def run(self, function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> Any:
        """Run a synchronous function with this policy."""
        ensure_sync_retryable_callable(function)
        return execute_sync(self, function, *args, **kwargs)

    async def run_async(
        self,
        function: Callable[P, Awaitable[T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Any:
        """Run an asynchronous function with this policy."""
        ensure_retryable_callable(function)
        return await execute_async(self, function, *args, **kwargs)

    # ---------------------------------------------- decorator / __call__

    @overload
    def __call__(
        self,
        function: Callable[P, T],
    ) -> RetryWrappedFunction[P, T | RetryResult[T]]: ...

    @overload
    def __call__(
        self,
        function: Callable[P, Awaitable[T]],
    ) -> RetryWrappedFunction[P, Awaitable[T | RetryResult[T]]]: ...

    def __call__(self, function: Callable[..., Any]) -> Callable[..., Any]:
        """
        Decorate a sync or async function.

        Decorated functions receive three extra attributes:
            - retry_stats: in-memory statistics for this function
            - retry_policy: the policy used by this function
            - with_policy(policy): re-decorate with a different policy
        """
        from relinker.internal.decorator import make_decorated

        return make_decorated(self, function)

    # ------------------------------------------ internal result resolution

    def _resolve_tracked_result(self, result: RetryResult[Any]) -> Any:
        """
        Convert a tracked RetryResult to the behavior configured by this policy.

        Used by the decorator so statistics can be collected regardless of the
        configured exhausted behavior.
        """
        from relinker.internal.exhaustion import resolve_tracked_result

        return resolve_tracked_result(self, result)
