from relinker import RetryPolicy


def test_policy_jitter_adds_to_existing_delay() -> None:
    policy = RetryPolicy().fixed_delay(1).jitter(minimum=0, maximum=1, seed=1)

    value = policy.delay_strategy.next_delay(1)

    assert 1 <= value <= 2


def test_policy_or_stop_after_time_keeps_attempt_limit() -> None:
    policy = RetryPolicy().attempts(3).or_stop_after_time(100)

    assert not policy.stop_strategy.should_stop(2, 1)
    assert policy.stop_strategy.should_stop(3, 1)


def test_policy_or_retry_if_result_combines_conditions() -> None:
    policy = RetryPolicy().on(TimeoutError).or_retry_if_result(lambda value: value is None)

    assert policy.condition.should_retry_exception(TimeoutError())
    assert policy.condition.should_retry_result(None)
