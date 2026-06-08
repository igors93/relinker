from collections.abc import Awaitable
from typing import Any

from typing_extensions import assert_type

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
assert_type(reconfigured(1, enabled=True), Any)
reconfigured_bad_arg = reconfigured("bad", enabled=True)  # type: ignore[arg-type]
reconfigured_bad_kwarg = reconfigured(1, enabled=1)  # type: ignore[arg-type]

normal_reconfigured = simple_retry.with_policy(RetryPolicy[str]().attempts(1))
assert_type(normal_reconfigured(1), Any)

sync_wrong_policy: RetryPolicy[int] = RetryPolicy[int]().attempts(2)
sync_changed_with_wrong_policy = simple_retry.with_policy(sync_wrong_policy)
assert_type(sync_changed_with_wrong_policy(1), Any)
sync_changed_with_wrong_policy_bad_arg = sync_changed_with_wrong_policy("bad")  # type: ignore[arg-type]

normal_to_result = simple_retry.with_policy(RetryPolicy[str]().return_result())
assert_type(normal_to_result(1), Any)

normal_to_result_wrong_policy = simple_retry.with_policy(RetryPolicy[int]().return_result())
assert_type(normal_to_result_wrong_policy(1), Any)

result_to_normal = result_retry.with_policy(RetryPolicy[str]().attempts(1))
assert_type(result_to_normal(1), Any)

result_to_normal_wrong_policy = result_retry.with_policy(RetryPolicy[int]().attempts(1))
assert_type(result_to_normal_wrong_policy(1), Any)

normal_to_fallback_wrong_policy = simple_retry.with_policy(RetryPolicy[int]().fallback_value(123))
assert_type(normal_to_fallback_wrong_policy(1), Any)

normal_to_custom_raise_wrong_policy = simple_retry.with_policy(
    RetryPolicy[int]().on_exhausted_raise(RuntimeError)
)
assert_type(normal_to_custom_raise_wrong_policy(1), Any)

async_normal_to_result = simple_async_retry.with_policy(RetryPolicy[str]().return_result())
assert_type(async_normal_to_result(1), Awaitable[Any])

async_wrong_policy: RetryPolicy[int] = RetryPolicy[int]().attempts(2)
async_changed_with_wrong_policy = simple_async_retry.with_policy(async_wrong_policy)
assert_type(async_changed_with_wrong_policy(1), Awaitable[Any])
async_changed_with_wrong_policy_bad_arg = async_changed_with_wrong_policy("bad")  # type: ignore[arg-type]

async_result_to_normal = result_async_retry.with_policy(RetryPolicy[str]().attempts(1))
assert_type(async_result_to_normal(1), Awaitable[Any])

method_to_result = Worker.sync_method.with_policy(RetryPolicy[str]().return_result())
assert_type(method_to_result(Worker(), 1), Any)
method_to_result_bad_arg = method_to_result(Worker(), "bad")  # type: ignore[arg-type]

method_wrong_policy = Worker.sync_method.with_policy(RetryPolicy[int]().attempts(1))
assert_type(method_wrong_policy(Worker(), 1), Any)
method_wrong_policy_bad_arg = method_wrong_policy(Worker(), "bad")  # type: ignore[arg-type]

async_method_wrong_policy = Worker.async_method.with_policy(RetryPolicy[int]().attempts(1))
assert_type(async_method_wrong_policy(Worker(), 1), Awaitable[Any])
async_method_wrong_policy_bad_arg = async_method_wrong_policy(Worker(), "bad")  # type: ignore[arg-type]
