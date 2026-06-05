"""
Retry policy builder.

RetryPolicy is the main public object in Relinker. It is an immutable builder:
every configuration method returns a new policy so it can be shared and reused
safely without side effects.

Implementation details are kept in the internal/ modules so this file remains a
readable public facade.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Any, Generic, Literal, cast, overload

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
from relinker.diagnostics import PolicyHealthReport, PolicyWarning, RetrySimulation
from relinker.event import EventHandler, EventName, RetryEvent
from relinker.exceptions import InvalidRetryConfigError
from relinker.executors.async_ import execute_async
from relinker.executors.sync import execute_sync
from relinker.internal.sleep import async_sleep as default_async_sleep
from relinker.internal.sleep import sleep as default_sleep
from relinker.result import RetryResult
from relinker.state import RetryState
from relinker.stop.attempts import StopAfterAttempt
from relinker.stop.base import StopStrategy
from relinker.stop.forever import StopForever
from relinker.stop.max_time import StopAfterDelay
from relinker.typing import P, T

ResultExhaustedBehavior = Literal["return_last", "raise"]
ExhaustedCallback = Callable[[RetryResult[Any]], Any]
ExceptionFactory = Callable[[RetryResult[Any]], BaseException]
StatefulDelayCallback = Callable[[RetryState], float]


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
    event_handlers: tuple[tuple[EventName, EventHandler], ...] = ()
    sleep: Callable[[float], None] = default_sleep
    async_sleep: Callable[[float], Awaitable[None]] = default_async_sleep
    history_limit: int | None = 1000

    def __post_init__(self) -> None:
        if self.history_limit is not None:
            from relinker.internal.validation import ensure_positive_int

            ensure_positive_int("history_limit", self.history_limit)

    # ------------------------------------------------------------------ stop

    def attempts(self, maximum: int) -> RetryPolicy[T]:
        """Return a new policy that stops after a maximum number of attempts."""
        return replace(self, stop_strategy=StopAfterAttempt(maximum))

    def forever(self) -> RetryPolicy[T]:
        """Return a new policy that never stops by attempt count."""
        return replace(self, stop_strategy=StopForever())

    def max_time(self, seconds: float) -> RetryPolicy[T]:
        """Return a new policy that stops after the given elapsed time."""
        return replace(self, stop_strategy=StopAfterDelay(seconds))

    def stop_when(self, strategy: StopStrategy) -> RetryPolicy[T]:
        """Return a new policy using a custom stop strategy."""
        return replace(self, stop_strategy=strategy)

    def or_stop_after_attempts(self, maximum: int) -> RetryPolicy[T]:
        """Return a new policy that stops on current strategy OR attempt limit."""
        from relinker.stop.composite import AnyStopStrategy

        return replace(
            self,
            stop_strategy=AnyStopStrategy((self.stop_strategy, StopAfterAttempt(maximum))),
        )

    def or_stop_after_time(self, seconds: float) -> RetryPolicy[T]:
        """Return a new policy that stops on current strategy OR elapsed time."""
        from relinker.stop.composite import AnyStopStrategy

        return replace(
            self,
            stop_strategy=AnyStopStrategy((self.stop_strategy, StopAfterDelay(seconds))),
        )

    def and_stop_after_attempts(self, maximum: int) -> RetryPolicy[T]:
        """Return a new policy that stops only when both strategies stop."""
        from relinker.stop.composite import AllStopStrategy

        return replace(
            self,
            stop_strategy=AllStopStrategy((self.stop_strategy, StopAfterAttempt(maximum))),
        )

    def and_stop_after_time(self, seconds: float) -> RetryPolicy[T]:
        """Return a new policy that stops only when both strategies stop."""
        from relinker.stop.composite import AllStopStrategy

        return replace(
            self,
            stop_strategy=AllStopStrategy((self.stop_strategy, StopAfterDelay(seconds))),
        )

    # ----------------------------------------------------------- conditions

    def on(self, *exception_types: type[BaseException]) -> RetryPolicy[T]:
        """Return a new policy that retries on the given exception types."""
        types = exception_types or (Exception,)
        return replace(self, condition=ExceptionCondition(types))

    def retry_if_result(self, predicate: Callable[[Any], bool]) -> RetryPolicy[T]:
        """Return a new policy that retries when a result predicate is true."""
        return replace(self, condition=ResultCondition(predicate))

    def retry_if(self, callback: Callable[[BaseException | None, Any], bool]) -> RetryPolicy[T]:
        """
        Return a new policy with a fully custom retry condition.

        The callback receives either an error or a value. Exactly one is non-None.
        """
        return replace(self, condition=CustomCondition(callback))

    def any_condition(self, *conditions: RetryCondition) -> RetryPolicy[T]:
        """Return a new policy that retries when any condition matches."""
        return replace(self, condition=AnyCondition(conditions))

    def all_conditions(self, *conditions: RetryCondition) -> RetryPolicy[T]:
        """Return a new policy that retries only when all conditions match."""
        return replace(self, condition=AllCondition(conditions))

    def or_on(self, *exception_types: type[BaseException]) -> RetryPolicy[T]:
        """Return a new policy that OR-combines current condition with exception retry."""
        return replace(
            self,
            condition=AnyCondition((self.condition, ExceptionCondition(exception_types))),
        )

    def or_retry_if_result(self, predicate: Callable[[Any], bool]) -> RetryPolicy[T]:
        """Return a new policy that OR-combines current condition with result retry."""
        return replace(
            self,
            condition=AnyCondition((self.condition, ResultCondition(predicate))),
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
        return replace(self, delay_strategy=AdditiveDelay((self.delay_strategy, jitter_delay)))

    def add_delay(self, strategy: DelayStrategy) -> RetryPolicy[T]:
        """Return a new policy that adds a delay strategy to the current strategy."""
        return replace(self, delay_strategy=AdditiveDelay((self.delay_strategy, strategy)))

    def custom_delay(self, callback: Callable[[int], float]) -> RetryPolicy[T]:
        """Return a new policy with a custom delay callback (receives attempt number)."""
        return replace(self, delay_strategy=CustomDelay(callback))

    def stateful_delay(self, callback: StatefulDelayCallback) -> RetryPolicy[T]:
        """
        Return a new policy with a state-aware delay callback.

        The callback receives a RetryState snapshot before each sleep and must
        return a non-negative float (seconds). This enables delays that adapt
        based on the last error, last value, elapsed time, or response headers.
        """
        return replace(self, delay_strategy=StatefulCustomDelay(callback))

    # -------------------------------------------------- exhausted behavior

    def raise_last(self) -> RetryPolicy[T]:
        """Return a new policy that re-raises the last original exception."""
        return replace(self, should_raise_last=True, should_return_result=False)

    def return_result(self) -> RetryPolicy[T]:
        """Return a new policy that returns RetryResult instead of raising."""
        return replace(self, should_return_result=True, should_raise_last=False)

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
        return replace(
            self,
            exhausted_callback=callback,
            exhausted_exception_factory=None,
            should_return_result=False,
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

            def make_from_class(result: RetryResult[Any]) -> BaseException:
                return exception("Retry attempts were exhausted.")

            resolved_factory = make_from_class
        elif isinstance(exception, BaseException):

            def make_from_instance(result: RetryResult[Any]) -> BaseException:
                return exception

            resolved_factory = make_from_instance
        elif callable(exception):
            resolved_factory = cast(ExceptionFactory, exception)
        else:
            raise InvalidRetryConfigError("exception must be an exception, class, or factory")

        return replace(
            self,
            exhausted_exception_factory=resolved_factory,
            exhausted_callback=None,
            should_return_result=False,
        )

    # --------------------------------------------------- history

    def keep_history(self, maximum: int | None) -> RetryPolicy[T]:
        """
        Return a new policy that retains at most maximum attempt records.

        - Positive integer: keep only the last N AttemptRecord objects in
          RetryResult.attempts and RetryState.attempts. Attempt numbers always
          count all attempts, even those not retained.
        - None: keep unlimited history (use with care for long-running policies).
        - Zero, negative values, and booleans are rejected.
        """
        if maximum is not None:
            from relinker.internal.validation import ensure_positive_int

            ensure_positive_int("maximum", maximum)
        return replace(self, history_limit=maximum)

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
        return replace(
            self,
            sleep=sleep,
            async_sleep=async_sleep if async_sleep is not None else self.async_sleep,
        )

    # ------------------------------------------------------------ events

    def on_event(self, name: EventName, handler: EventHandler) -> RetryPolicy[T]:
        """Return a new policy with an additional event handler."""
        return replace(self, event_handlers=(*self.event_handlers, (name, handler)))

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

    def debug(self) -> RetryPolicy[T]:
        """Return a new policy with simple console debug events enabled."""

        def print_event(event: RetryEvent) -> None:
            if event.name == "before_attempt":
                print(f"[relinker] attempt {event.attempt_number} started: {event.function_name}")
            elif event.name == "after_failure" and event.error is not None:
                message = (
                    f"[relinker] attempt {event.attempt_number} failed: "
                    f"{event.error.__class__.__name__}: {event.error}"
                )
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
            policy = policy.on_event(event_name, print_event)
        return policy

    def with_logging(
        self,
        *,
        level: int = logging.WARNING,
        logger: logging.Logger | None = None,
    ) -> RetryPolicy[T]:
        """
        Return a new policy that logs retry activity using the standard library.

        Logs before each sleep and after giving up. Successful first attempts are
        not logged to avoid noise.
        """
        from relinker.internal.policy_logging import make_logging_handler

        _logger = logger if logger is not None else logging.getLogger("relinker")
        handler = make_logging_handler(level, _logger)
        policy: RetryPolicy[T] = self
        for event_name in ("before_sleep", "after_giveup"):
            policy = policy.on_event(event_name, handler)
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
            policy = policy.on_event(event_name, handler)
        return policy

    def emit(self, event: RetryEvent) -> None:
        """Emit an event to all matching handlers."""
        for name, handler in self.event_handlers:
            if name == event.name:
                handler(event)

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

        The simulation is advisory and deterministic for fixed delays. For
        StatefulCustomDelay, it uses a minimal state (no last_value/error).
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

    def preview(self, attempts: int = 5) -> str:
        """Return a concise preview of retry timing and policy warnings."""
        from relinker.internal.policy_simulation import preview_policy

        return preview_policy(self, attempts)

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
        return execute_sync(self, function, *args, **kwargs)

    async def run_async(
        self,
        function: Callable[P, Awaitable[T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Any:
        """Run an asynchronous function with this policy."""
        return await execute_async(self, function, *args, **kwargs)

    # ---------------------------------------------- decorator / __call__

    @overload
    def __call__(self, function: Callable[P, T]) -> Callable[P, T]: ...

    @overload
    def __call__(self, function: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]: ...

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
