from relinker.delays.custom import CustomDelay


def test_custom_delay() -> None:
    delay = CustomDelay(lambda attempt: attempt * 2)

    assert delay.next_delay(3) == 6
