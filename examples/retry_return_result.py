from retryflow import RetryPolicy


def task() -> str:
    raise RuntimeError("temporary failure")


result = RetryPolicy().attempts(2).return_result().run(task)

print(result.story())
