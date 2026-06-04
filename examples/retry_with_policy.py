from retryflow import RetryPolicy


policy = (
    RetryPolicy()
    .attempts(3)
    .on(RuntimeError)
    .fixed_delay(0.1)
    .debug()
)


@policy
def task() -> str:
    return "ok"


print(policy.explain())
print(task())
