"""
Retry policy builder.

RetryPolicy is the main object in RetryFlow. It is intentionally designed as a
small, explicit, immutable builder. Every configuration method returns a new
policy, which avoids surprising side effects when policies are reused.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from functools import wraps
from typing import Any, Generic, Literal, cast, overload

from retryflow.conditions.base import RetryCondition
from retryflow.conditions.composite import AllCondition, AnyCondition
from retryflow.conditions.custom import CustomCondition
from retryflow.conditions.exception import ExceptionCondition
from retryflow.conditions.result import ResultCondition
from retryflow.context import AsyncRetryBlockIterator, RetryBlockIterator
from retryflow.delays.base import DelayStrategy
from retryflow.delays.chain import ChainDelay
from retryflow.delays.composite import AdditiveDelay
from retryflow.delays.custom import CustomDelay
from retryflow.delays.exponential import ExponentialDelay
from retryflow.delays.fixed import FixedDelay
from retryflow.delays.linear import LinearDelay
from retryflow.delays.random_delay import RandomDelay
from retryflow.delays.random_exponential import RandomExponentialDelay
from retryflow.event import EventHandler, EventName, RetryEvent
from retryflow.exceptions import InvalidRetryConfigError, RetryExhaustedError
from retryflow.executors.async_ import execute_async
from retryflow.executors.sync import execute_sync
from retryflow.internal.sleep import async_sleep as default_async_sleep
from retryflow.internal.sleep import sleep as default_sleep
from retryflow.result import RetryResult
from retryflow.stats import RetryStats
from retryflow.stop.attempts import StopAfterAttempt
from retryflow.stop.base import StopStrategy
from retryflow.stop.composite import AllStopStrategy, AnyStopStrategy
from retryflow.stop.forever import StopForever
from retryflow.stop.max_time import StopAfterDelay
from retryflow.typing import P, T

ResultExhaustedBehavior = Literal["return_last", "raise"]
ExhaustedCallback = Callable[[RetryResult[Any]], Any]
ExceptionFactory = Callable[[RetryResult[Any]], BaseException]


@dataclass(frozen=True, slots=True)
class RetryPolicy(Generic[T]):
    """
    Immutable retry policy.

    The policy stores what should happen, but the executors perform the actual
    running. This separation keeps configuration and execution easy to maintain.
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
        return replace(
            self,
            stop_strategy=AnyStopStrategy((self.stop_strategy, StopAfterAttempt(maximum))),
        )

    def or_stop_after_time(self, seconds: float) -> RetryPolicy[T]:
        """Return a new policy that stops on current strategy OR elapsed time."""
        return replace(
            self,
            stop_strategy=AnyStopStrategy((self.stop_strategy, StopAfterDelay(seconds))),
        )

    def and_stop_after_attempts(self, maximum: int) -> RetryPolicy[T]:
        """Return a new policy that stops only when both strategies stop."""
        return replace(
            self,
            stop_strategy=AllStopStrategy((self.stop_strategy, StopAfterAttempt(maximum))),
        )

    def and_stop_after_time(self, seconds: float) -> RetryPolicy[T]:
        """Return a new policy that stops only when both strategies stop."""
        return replace(
            self,
            stop_strategy=AllStopStrategy((self.stop_strategy, StopAfterDelay(seconds))),
        )

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
        """Return a new policy with a custom delay callback."""
        return replace(self, delay_strategy=CustomDelay(callback))

    def raise_last(self) -> RetryPolicy[T]:
        """Return a new policy that re-raises the last original exception."""
        return replace(self, should_raise_last=True, should_return_result=False)

    def return_result(self) -> RetryPolicy[T]:
        """Return a new policy that returns RetryResult instead of raising."""
        return replace(self, should_return_result=True, should_raise_last=False)

    def raise_on_result_exhausted(self) -> RetryPolicy[T]:
        """
        Return a new policy that raises RetryExhaustedError when result retry is exhausted.

        This is optional. The default behavior keeps user freedom and returns the
        last value for result-based retries unless `return_result()` is enabled.
        """
        return replace(self, result_exhausted_behavior="raise")

    def return_last_on_result_exhausted(self) -> RetryPolicy[T]:
        """Return a new policy that returns the last value when result retry is exhausted."""
        return replace(self, result_exhausted_behavior="return_last")

    def on_exhausted_return(self, callback: ExhaustedCallback) -> RetryPolicy[T]:
        """
        Return a new policy that calls a callback when retry attempts are exhausted.

        The callback receives RetryResult and its return value becomes the final
        return value. This is useful for fallbacks.
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

    def with_sleep(
        self,
        sleep: Callable[[float], None],
        async_sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> RetryPolicy[T]:
        """
        Return a new policy with custom sleep functions.

        This is useful for tests, simulations, and advanced integrations.
        """
        return replace(
            self,
            sleep=sleep,
            async_sleep=async_sleep if async_sleep is not None else self.async_sleep,
        )

    def on_event(self, name: EventName, handler: EventHandler) -> RetryPolicy[T]:
        """Return a new policy with an additional event handler."""
        return replace(self, event_handlers=(*self.event_handlers, (name, handler)))

    def debug(self) -> RetryPolicy[T]:
        """Return a new policy with simple console debug events enabled."""

        def print_event(event: RetryEvent) -> None:
            if event.name == "before_attempt":
                print(f"[retryflow] attempt {event.attempt_number} started: {event.function_name}")
            elif event.name == "after_failure" and event.error is not None:
                message = (
                    f"[retryflow] attempt {event.attempt_number} failed: "
                    f"{event.error.__class__.__name__}: {event.error}"
                )
                print(message)
            elif event.name == "before_sleep" and event.delay is not None:
                print(f"[retryflow] sleeping {event.delay:.4f}s before next attempt")
            elif event.name == "after_success":
                print(f"[retryflow] attempt {event.attempt_number} succeeded")
            elif event.name == "after_giveup":
                print(f"[retryflow] giving up after attempt {event.attempt_number}")

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

    def emit(self, event: RetryEvent) -> None:
        """Emit an event to all matching handlers."""
        for name, handler in self.event_handlers:
            if name == event.name:
                handler(event)

    def explain(self) -> str:
        """Return a readable explanation of this policy."""
        return "\n".join(
            [
                "RetryFlow policy",
                "",
                f"Stop strategy: {self.stop_strategy.__class__.__name__}",
                f"Delay strategy: {self.delay_strategy.__class__.__name__}",
                f"Condition: {self.condition.__class__.__name__}",
                f"Raise last exception: {self.should_raise_last}",
                f"Return RetryResult: {self.should_return_result}",
                f"Result exhausted behavior: {self.result_exhausted_behavior}",
                f"Has exhausted callback: {self.exhausted_callback is not None}",
                f"Has exhausted exception factory: {self.exhausted_exception_factory is not None}",
                f"Event handlers: {len(self.event_handlers)}",
            ]
        )

    def timeline(self, attempts: int = 5) -> str:
        """
        Return an estimated delay timeline.

        This method does not execute the function. It only helps users understand
        the selected delay strategy.
        """
        lines = ["RetryFlow estimated timeline", ""]
        for attempt_number in range(1, attempts + 1):
            delay = self.delay_strategy.next_delay(attempt_number)
            lines.append(f"After attempt {attempt_number}: wait {delay:.4f}s")
        return "\n".join(lines)

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

    def _resolve_tracked_result(self, result: RetryResult[Any]) -> Any:
        """
        Convert a tracked RetryResult back to the behavior configured by this policy.

        Decorated functions use this method so RetryFlow can always collect
        statistics while preserving the user's chosen return/raise behavior.
        """
        if self.should_return_result:
            return result

        if result.exhausted:
            if self.exhausted_callback is not None:
                return self.exhausted_callback(result)

            if self.exhausted_exception_factory is not None:
                raise self.exhausted_exception_factory(result)

            if result.error is not None and self.should_raise_last:
                raise result.error

            if result.exhausted_by_result and self.result_exhausted_behavior == "raise":
                raise RetryExhaustedError(
                    "Retry attempts were exhausted by rejected return values.",
                    result=result,
                )

            return result.value

        if result.error is not None:
            if self.should_raise_last:
                raise result.error
            return None

        return result.value

    @overload
    def __call__(self, function: Callable[P, T]) -> Callable[P, T]: ...

    @overload
    def __call__(self, function: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]: ...

    def __call__(self, function: Callable[..., Any]) -> Callable[..., Any]:
        """
        Decorate a sync or async function.

        Decorated functions receive:
            - retry_stats: in-memory statistics
            - retry_policy: the policy used by the function
            - with_policy(policy): helper to decorate the same function with another policy
        """
        import inspect

        stats = RetryStats()

        def with_policy(policy: RetryPolicy[Any]) -> Callable[..., Any]:
            return policy(function)

        if inspect.iscoroutinefunction(function):

            @wraps(function)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracking_policy = self.return_result()
                result = await tracking_policy.run_async(function, *args, **kwargs)
                stats.record(result)
                return self._resolve_tracked_result(result)

            async_wrapper_any = cast(Any, async_wrapper)
            async_wrapper_any.retry_stats = stats
            async_wrapper_any.retry_policy = self
            async_wrapper_any.with_policy = with_policy
            return async_wrapper

        @wraps(function)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracking_policy = self.return_result()
            result = tracking_policy.run(function, *args, **kwargs)
            stats.record(result)
            return self._resolve_tracked_result(result)

        sync_wrapper_any = cast(Any, sync_wrapper)
        sync_wrapper_any.retry_stats = stats
        sync_wrapper_any.retry_policy = self
        sync_wrapper_any.with_policy = with_policy
        return sync_wrapper
