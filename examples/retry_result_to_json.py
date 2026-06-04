from retryflow import RetryPolicy


def task() -> str:
    return "ok"


if __name__ == "__main__":
    result = RetryPolicy().attempts(1).return_result().run(task)
    print(result.to_json(indent=2))
