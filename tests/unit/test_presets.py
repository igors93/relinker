import pytest

from relinker import background_job, database, fast, network, patient
from relinker.presets import network as network_from_module


def test_fast_preset_returns_policy() -> None:
    policy = fast()

    assert policy.stop_strategy.should_stop(3, 0)
    assert policy.delay_strategy.next_delay(1) == 0.1


def test_network_preset_uses_expected_defaults() -> None:
    policy = network()

    assert policy.stop_strategy.should_stop(5, 0)
    assert policy.condition.should_retry_exception(TimeoutError())
    assert policy.condition.should_retry_exception(ConnectionError())
    assert policy.condition.should_retry_exception(OSError())


def test_database_preset_uses_expected_defaults() -> None:
    policy = database()

    assert policy.stop_strategy.should_stop(4, 0)
    assert policy.condition.should_retry_exception(ConnectionError())


def test_patient_preset_uses_expected_defaults() -> None:
    policy = patient()

    assert policy.stop_strategy.should_stop(8, 0)
    assert policy.condition.should_retry_exception(TimeoutError())


def test_background_job_preset_warns_about_broad_exception() -> None:
    policy = background_job()

    codes = {warning.code for warning in policy.warnings()}

    assert "broad_exception" in codes


def test_presets_accept_custom_exception_types() -> None:
    policy = network_from_module(TimeoutError)

    assert policy.condition.should_retry_exception(TimeoutError())
    assert not policy.condition.should_retry_exception(ConnectionError())


@pytest.mark.parametrize("factory", [network, database, patient])
def test_broad_transport_presets_preserve_os_error_retry_and_warn(factory) -> None:
    policy = factory()

    assert policy.condition.should_retry_exception(OSError("temporary"))
    assert "broad_os_error" in {warning.code for warning in policy.warnings()}
