from retryflow import RetryPolicy

policy = RetryPolicy().attempts(2).on(TimeoutError).fallback_value("safe fallback")


@policy
def call_service() -> str:
    raise TimeoutError("service unavailable")


if __name__ == "__main__":
    print(call_service())
