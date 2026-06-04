"""
Example: Using the built-in logging helper.

with_logging() connects RetryFlow to Python's standard logging system.
No external dependencies are needed.
"""

from __future__ import annotations

import logging

from retryflow import RetryPolicy
from retryflow.testing import no_sleep

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)


# --- Example 1: default logging with WARNING level ---


def example_default_logging() -> None:
    print("=== Default logging (WARNING) ===")
    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 3:
            raise TimeoutError("connection timeout")
        return "ok"

    policy = RetryPolicy().attempts(5).on(TimeoutError).fixed_delay(0).with_logging()

    with no_sleep():
        result = policy.run(task)

    print(f"Result: {result}")


# --- Example 2: INFO level logging ---


def example_info_logging() -> None:
    print("\n=== INFO logging ===")
    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 2:
            raise ConnectionError("no route to host")
        return "connected"

    policy = (
        RetryPolicy()
        .attempts(5)
        .on(ConnectionError)
        .fixed_delay(0)
        .with_logging(level=logging.INFO)
    )

    with no_sleep():
        result = policy.run(task)

    print(f"Result: {result}")


# --- Example 3: custom logger ---


def example_custom_logger() -> None:
    print("\n=== Custom logger ===")
    logger = logging.getLogger("my_app.payments")

    def task() -> str:
        raise OSError("payment gateway unavailable")

    policy = (
        RetryPolicy()
        .attempts(3)
        .on(OSError)
        .fixed_delay(0)
        .with_logging(level=logging.ERROR, logger=logger)
    )

    try:
        with no_sleep():
            policy.run(task)
    except OSError as e:
        print(f"Caught: {e}")


# --- Example 4: logging + debug for full visibility ---


def example_logging_with_debug() -> None:
    print("\n=== Logging + debug events ===")
    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 2:
            raise ValueError("bad input")
        return "fixed"

    policy = (
        RetryPolicy()
        .attempts(3)
        .on(ValueError)
        .fixed_delay(0)
        .with_logging(level=logging.INFO)
        .debug()  # also prints to stdout
    )

    with no_sleep():
        result = policy.run(task)

    print(f"Result: {result}")


if __name__ == "__main__":
    example_default_logging()
    example_info_logging()
    example_custom_logger()
    example_logging_with_debug()
