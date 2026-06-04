from retryflow import retry


@retry(attempts=3, delay=0.1)
def unstable_task() -> str:
    return "ok"


if __name__ == "__main__":
    print(unstable_task())
