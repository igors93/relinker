from retryflow import RetryPolicy


def test_policy_explain_contains_key_parts() -> None:
    policy = RetryPolicy().attempts(3).fixed_delay(1)
    explanation = policy.explain()

    assert "RetryFlow policy" in explanation
    assert "StopAfterAttempt" in explanation
    assert "FixedDelay" in explanation
