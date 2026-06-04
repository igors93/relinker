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
from typing import Any, Generic, Literal, overload

from retryflow.conditions.base import RetryCondition
from retryflow.conditions.custom import CustomCondition
from retryflow.conditions.exception import ExceptionCondition
from retryflow.conditions.result import ResultCondition
from retryflow.delays.base import DelayStrategy
from retryflow.delays.custom import CustomDelay
from retryflow.delays.exponential import ExponentialDelay
from retryflow.delays.fixed import FixedDelay
from retryflow.delays.random_delay import RandomDelay
from retryflow.event import EventHandler, EventName, RetryEvent
from retryflow.executors.async_ import execute_async
from retryflow.executors.sync import execute_sync
from retryflow.internal.sleep import async_sleep as default_async_sleep
from retryflow.internal.sleep import sleep as default_sleep
from retryflow.stop.attempts import StopAfterAttempt
from retryflow.stop.forever import StopForever
from retryflow.stop.max_time import StopAfterDelay
from retryflow.typing import P, T

ResultExhaustedBehavior = Literal["return_last", "raise"]


@dataclass(frozen=True, slots=True)
class RetryPolicy(Generic[T]):
    """
    Immutable retry policy.

    The policy stores what should happen, but the executors perform the actual
    running. This separation keeps configuration and execution easy to maintain.
    """

    stop_strategy: Any = StopAfterAttempt(3)
    delay_strategy: DelayStrategy = FixedDelay(0)
    condition: RetryCondition = ExceptionCondition((Exception,))
    should_raise_last: bool = True
    should_return_result: bool = False
    result_exhausted_behavior: ResultExhaustedBehavior = "return_last"
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

    def fixed_delay(self, seconds: float) -> RetryPolicy[T]:
        """Return a new policy with a fixed delay strategy."""
        return replace(self, delay_strategy=FixedDelay(seconds))

    def no_delay(self) -> RetryPolicy[T]:
        """Return a new policy with zero delay."""
        return self.fixed_delay(0)

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

    @overload
    def __call__(self, function: Callable[P, T]) -> Callable[P, T]: ...

    @overload
    def __call__(self, function: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]: ...

    def __call__(self, function: Callable[..., Any]) -> Callable[..., Any]:
        """
        Decorate a sync or async function.

        RetryFlow detects coroutine functions and routes them to the async executor.
        """
        import inspect

        if inspect.iscoroutinefunction(function):

            @wraps(function)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await self.run_async(function, *args, **kwargs)

            return async_wrapper

        @wraps(function)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.run(function, *args, **kwargs)

        return sync_wrapper
