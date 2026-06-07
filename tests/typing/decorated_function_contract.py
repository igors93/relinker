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
