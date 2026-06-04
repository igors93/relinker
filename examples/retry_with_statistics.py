from retryflow import fast


@fast()
def task() -> str:
    return "ok"


if __name__ == "__main__":
    task()
    task()
    print(task.retry_stats.to_dict())
