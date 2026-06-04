from retryflow import RetryPolicy


def test_policy_linear_delay() -> None:
    policy = RetryPolicy().linear_delay(start=1, step=2, maximum=5)

    assert policy.delay_strategy.next_delay(1) == 1
    assert policy.delay_strategy.next_delay(2) == 3
    assert policy.delay_strategy.next_delay(3) == 5


def test_policy_chain_delay() -> None:
    policy = RetryPolicy().chain_delay([1, 2])

    assert policy.delay_strategy.next_delay(1) == 1
    assert policy.delay_strategy.next_delay(2) == 2
    assert policy.delay_strategy.next_delay(3) == 2


def test_policy_random_exponential_delay() -> None:
    policy = RetryPolicy().random_exponential_delay(base=1, maximum=10, seed=1)

    assert 0 <= policy.delay_strategy.next_delay(1) <= 1
