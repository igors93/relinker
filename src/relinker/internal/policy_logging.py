"""
Logging integration for retry policies.

Implements handler factories for RetryPolicy.with_logging() and
RetryPolicy.with_structured_logging(). This is internal; the public API remains
on RetryPolicy.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from relinker.event import EventHandler, RetryEvent


def make_logging_handler(
    level: int,
    logger: logging.Logger,
    *,
    include_error_message: bool = False,
) -> EventHandler:
    """
    Create an event handler that logs retry activity to a standard-library logger.

    Logs before each sleep (failure + upcoming retry) and after giveup/exhaustion.
    Successful attempts are not logged by default to keep noise low.

    Error messages are excluded by default because they may contain secrets,
    tokens, URLs, or payload fragments. Set ``include_error_message=True``
    when you explicitly need the message text and have verified it is safe to log.
    """

    def handler(event: RetryEvent) -> None:
        policy_label = f" policy={event.policy_name}" if event.policy_name else ""
        if event.name == "before_sleep":
            logger.log(
                level,
                "Attempt %d failed (%s), retrying in %.2fs%s",
                event.attempt_number,
                event.error.__class__.__name__ if event.error is not None else "result rejected",
                event.delay if event.delay is not None else 0.0,
                policy_label,
            )
        elif event.name == "after_giveup":
            if event.error is not None:
                if include_error_message:
                    logger.log(
                        level,
                        "Giving up after attempt %d: %s: %s%s",
                        event.attempt_number,
                        event.error.__class__.__name__,
                        event.error,
                        policy_label,
                    )
                else:
                    logger.log(
                        level,
                        "Giving up after attempt %d: %s%s",
                        event.attempt_number,
                        event.error.__class__.__name__,
                        policy_label,
                    )
            else:
                logger.log(
                    level,
                    "Giving up after attempt %d: result retry exhausted%s",
                    event.attempt_number,
                    policy_label,
                )

    return handler


def make_structured_logging_handler(
    level: int,
    logger: logging.Logger,
    *,
    include_error_message: bool = False,
) -> EventHandler:
    """
    Create a JSON logging handler with safe default fields.

    Error messages can contain secrets or user data, so they are excluded unless
    include_error_message=True is explicitly requested by the caller.
    """

    def handler(event: RetryEvent) -> None:
        payload = _structured_payload(event, include_error_message=include_error_message)
        logger.log(level, "%s", json.dumps(payload, sort_keys=True, separators=(",", ":")))

    return handler


def _structured_payload(
    event: RetryEvent,
    *,
    include_error_message: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "library": "relinker",
        "event": event.name,
        "function": event.function_name,
        "attempt": event.attempt_number,
    }
    if event.policy_name is not None:
        payload["policy"] = event.policy_name

    if event.delay is not None:
        payload["delay"] = event.delay

    if event.error is not None:
        payload["error_type"] = event.error.__class__.__name__
        if include_error_message:
            payload["error_message"] = str(event.error)

    if event.state is not None:
        payload.update(
            {
                "elapsed": round(event.state.elapsed, 6),
                "attempt_count": event.state.attempt_count,
                "retry_cause": event.state.retry_cause,
                "will_retry": event.state.will_retry,
                "will_stop": event.state.will_stop,
            }
        )
        if event.state.policy_delay is not None:
            payload["policy_delay"] = event.state.policy_delay
        if event.state.budget_delay is not None:
            payload["budget_delay"] = event.state.budget_delay
        if event.state.next_delay is not None:
            payload["total_delay"] = event.state.next_delay

    return payload
