from retryflow import RetryPolicy
from retryflow.testing import no_sleep


policy = RetryPolicy().attempts(3).fixed_delay(10)

with no_sleep(policy) as fast_policy:
    result = fast_policy.return_result().run(lambda: "ok")

print(result.story())
