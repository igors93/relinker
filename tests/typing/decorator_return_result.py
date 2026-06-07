from relinker import RetryResult, retry


@retry
def default_value() -> str:
    return "value"


default_result: str = default_value()


@retry(return_result=False)
def explicit_false_value() -> str:
    return "value"


explicit_false_result: str = explicit_false_value()


@retry(return_result=True)
def result_value() -> str:
    return "value"


result_result: RetryResult[str] = result_value()


@retry(return_result=True)
def result_with_arguments(name: str, count: int) -> str:
    return f"{name}:{count}"


argument_result: RetryResult[str] = result_with_arguments("item", 3)


@retry(return_result=True)
async def async_result_value() -> str:
    return "value"


async def use_async_result_value() -> RetryResult[str]:
    return await async_result_value()


def choose_return_result() -> bool:
    return False


dynamic_return_result = choose_return_result()


@retry(return_result=dynamic_return_result)
def dynamic_result_value() -> str:
    return "value"


dynamic_result: str | RetryResult[str] = dynamic_result_value()
