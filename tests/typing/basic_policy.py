from relinker import RetryPolicy


def parse_number(value: str) -> int:
    return int(value)


policy: RetryPolicy[int] = RetryPolicy[int]().attempts(3).on(ValueError).no_delay()
parsed: int = policy.run(parse_number, "42")


def use_basic_policy() -> int:
    return parsed
