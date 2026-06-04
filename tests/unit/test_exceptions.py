import pytest

from retryflow import InvalidRetryConfigError, RetryPolicy


def test_invalid_attempts_raise_library_error() -> None:
    with pytest.raises(InvalidRetryConfigError):
        RetryPolicy().attempts(0)
