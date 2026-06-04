from retryflow import retry


@retry(attempts=3, delay=0.2)
def unstable_task() -> str:
    return "ok"


print(unstable_task())
