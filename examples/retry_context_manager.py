from retryflow import RetryPolicy

policy = RetryPolicy().attempts(3).on(RuntimeError)

calls = 0

for attempt in policy.iter(name="example_block"):
    with attempt:
        calls += 1
        if calls < 2:
            raise RuntimeError("temporary failure")

if __name__ == "__main__":
    print(f"succeeded after {calls} attempts")
