from relinker import retry


@retry(attempts=3, delay=0, on=(ValueError,))
def parse_number(value: str) -> int:
    return int(value)


parsed: int = parse_number("42")


def use_decorated_function() -> int:
    return parsed
