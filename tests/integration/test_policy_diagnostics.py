from retryflow import RetryPolicy


def test_policy_warnings_for_risky_configuration() -> None:
    policy = RetryPolicy().forever().on(Exception).no_delay()

    codes = {warning.code for warning in policy.warnings()}

    assert "forever" in codes
    assert "no_delay" in codes
    assert "broad_exception" in codes


def test_policy_simulate_returns_delay_timeline() -> None:
    simulation = RetryPolicy().attempts(3).fixed_delay(2).simulate(attempts=5)

    assert len(simulation.attempts) == 3
    assert simulation.attempts[0].delay_before_next_attempt == 2
    assert simulation.attempts[-1].stops_after_attempt
    assert simulation.total_sleep == 4


def test_timeline_uses_simulation_description() -> None:
    text = RetryPolicy().attempts(2).fixed_delay(1).timeline(attempts=3)

    assert "RetryFlow simulation" in text
    assert "Total simulated sleep" in text
