"""
Logging integration for retry policies.

Implements the handler factory for RetryPolicy.with_logging(). This is internal;
the public API is RetryPolicy.with_logging().
"""

from __future__ import annotations

import logging

from retryflow.event import EventHandler, RetryEvent


def make_logging_handler(
    level: int,
    logger: logging.Logger,
) -> EventHandler:
    """
    Create an event handler that logs retry activity to a standard-library logger.

    Logs before each sleep (failure + upcoming retry) and after giveup/exhaustion.
    Successful attempts are not logged by default to keep noise low.
    """

    def handler(event: RetryEvent) -> None:
        if event.name == "before_sleep":
            logger.log(
                level,
                "Attempt %d failed (%s), retrying in %.2fs",
                event.attempt_number,
                event.error.__class__.__name__ if event.error is not None else "result rejected",
                event.delay if event.delay is not None else 0.0,
            )
        elif event.name == "after_giveup":
            if event.error is not None:
                logger.log(
                    level,
                    "Giving up after attempt %d: %s: %s",
                    event.attempt_number,
                    event.error.__class__.__name__,
                    event.error,
                )
            else:
                logger.log(
                    level,
                    "Giving up after attempt %d: result retry exhausted",
                    event.attempt_number,
                )

    return handler
