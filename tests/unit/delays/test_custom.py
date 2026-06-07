import pytest

from relinker.delays.custom import CustomDelay
from relinker.exceptions import InvalidRetryConfigError


def test_custom_delay() -> None:
    delay = CustomDelay(lambda attempt: attempt * 2)

    assert delay.next_delay(3) == 6


def test_custom_delay_rejects_boolean_result() -> None:
    delay = CustomDelay(lambda attempt: True)

    with pytest.raises(
        InvalidRetryConfigError,
        match="resolved delay must be a finite non-negative number",
    ):
        delay.next_delay(1)


def test_custom_delay_rejects_string_result() -> None:
    delay = CustomDelay(lambda attempt: "2.5")  # type: ignore[return-value]

    with pytest.raises(
        InvalidRetryConfigError,
        match="resolved delay must be a finite non-negative number",
    ):
        delay.next_delay(1)