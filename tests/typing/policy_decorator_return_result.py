from relinker import RetryPolicy, RetryResult

result_policy = RetryPolicy[str]().return_result()


@result_policy
def result_value() -> str:
    return "value"


result_output: str | RetryResult[str] = result_value()

# A policy pode retornar RetryResult, portanto tratá-la sempre como str
# deve produzir um erro de tipagem.
incorrect_string_output: str = result_value()  # type: ignore[assignment]


async_result_policy = RetryPolicy[str]().return_result()


@async_result_policy
async def async_result_value() -> str:
    return "value"


async def use_async_result() -> None:
    result: str | RetryResult[str] = await async_result_value()

    incorrect: str = await async_result_value()  # type: ignore[assignment]

    assert isinstance(result, (str, RetryResult))
    assert isinstance(incorrect, str)
