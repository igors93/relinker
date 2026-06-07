from collections.abc import Awaitable

from relinker import RetryPolicy, RetryResult, retry
from relinker.stats import RetryStatsSnapshot

policy: RetryPolicy[str] = RetryPolicy[str]().attempts(2)


@policy
def sync_task(value: int, *, enabled: bool = True) -> str:
    return str(value) if enabled else "disabled"


@policy
async def async_task(value: int) -> str:
    return str(value)


@retry
def simple_retry(value: int) -> str:
    return str(value)


@retry(attempts=2, delay=0, on=(ValueError,))
def configured_retry(value: int) -> str:
    return str(value)


@retry(attempts=2, delay=0, on=(ValueError,), return_result=True)
def result_retry(value: int) -> str:
    return str(value)


@retry
async def simple_async_retry(value: int) -> str:
    return str(value)


@retry(return_result=True)
async def result_async_retry(value: int) -> str:
    return str(value)


class Worker:
    @retry(attempts=2, delay=0)
    def sync_method(self, value: int) -> str:
        return str(value)

    @retry(attempts=2, delay=0)
    async def async_method(self, value: int) -> str:
        return str(value)


sync_value: str | RetryResult[str] = sync_task(1)
sync_named_value: str | RetryResult[str] = sync_task(1, enabled=False)
async_value: Awaitable[str | RetryResult[str]] = async_task(1)
simple_value: str = simple_retry(1)
configured_value: str = configured_retry(1)
result_value: RetryResult[str] = result_retry(1)
method_value: str = Worker().sync_method(1)
async_method_value: Awaitable[str] = Worker().async_method(1)

snapshot: RetryStatsSnapshot = sync_task.retry_stats.snapshot()
policy_reference: RetryPolicy[object] = sync_task.retry_policy
reconfigured = sync_task.with_policy(RetryPolicy[str]().attempts(1))
reconfigured_value: str | RetryResult[str] = reconfigured(1, enabled=True)
reconfigured_bad_arg = reconfigured("bad", enabled=True)  # type: ignore[arg-type]
reconfigured_bad_kwarg = reconfigured(1, enabled=1)  # type: ignore[arg-type]

normal_reconfigured = simple_retry.with_policy(RetryPolicy[str]().attempts(1))
normal_reconfigured_value: str | RetryResult[str] = normal_reconfigured(1)

normal_to_result = simple_retry.with_policy(RetryPolicy[str]().return_result())
normal_to_result_value: str | RetryResult[str] = normal_to_result(1)
normal_to_result_incorrect: str = normal_to_result(1)  # type: ignore[assignment]

result_to_normal = result_retry.with_policy(RetryPolicy[str]().attempts(1))
result_to_normal_value: str | RetryResult[str] = result_to_normal(1)
result_to_normal_incorrect: RetryResult[str] = result_to_normal(1)  # type: ignore[assignment]

async_normal_to_result = simple_async_retry.with_policy(RetryPolicy[str]().return_result())
async_normal_to_result_value: Awaitable[str | RetryResult[str]] = async_normal_to_result(1)
async_normal_to_result_incorrect: Awaitable[str] = async_normal_to_result(1)  # type: ignore[assignment]

async_result_to_normal = result_async_retry.with_policy(RetryPolicy[str]().attempts(1))
async_result_to_normal_value: Awaitable[str | RetryResult[str]] = async_result_to_normal(1)
async_result_to_normal_incorrect: Awaitable[RetryResult[str]] = async_result_to_normal(1)  # type: ignore[assignment]

method_to_result = Worker.sync_method.with_policy(RetryPolicy[str]().return_result())
method_to_result_value: str | RetryResult[str] = method_to_result(Worker(), 1)
method_to_result_bad_arg = method_to_result(Worker(), "bad")  # type: ignore[arg-type]
method_to_result_incorrect: str = method_to_result(Worker(), 1)  # type: ignore[assignment]
