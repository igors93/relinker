"""
Dependency-free HTTP helpers for retry policies.

These helpers make it easy to build HTTP-aware retry policies without adding
any runtime dependencies. They work with any HTTP library or custom response
object that exposes a status code.

Idempotency note:
    Retrying HTTP requests is safe for idempotent methods (GET, HEAD, PUT,
    DELETE, OPTIONS). Retrying POST, PATCH, or other non-idempotent methods
    can cause duplicate side effects. RetryFlow does not block non-idempotent
    retries, but this module documents the concern so users can decide.

Retry-After note:
    The current delay strategy architecture passes only the attempt number to
    delay functions. It does not have access to the last response object.
    If you need to honour a Retry-After header, use the before_sleep event to
    read the header and adjust your delay externally, or store the parsed value
    in a shared variable that a custom_delay callback reads.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from email.utils import mktime_tz, parsedate_tz
from typing import Any


def should_retry_http_status(status_code: int, statuses: Iterable[int]) -> bool:
    """Return True when status_code is in the provided collection of retryable statuses.

    Example:
        if should_retry_http_status(response.status_code, {429, 500, 502, 503}):
            raise RetryableError()
    """
    return status_code in frozenset(statuses)


def retry_if_status(statuses: Iterable[int]) -> Callable[[Any], bool]:
    """
    Return a result predicate for use with policy.retry_if_result().

    The predicate returns True (retry) when the response's status code is in
    the given set. Supports:

    - Objects with a ``.status_code`` attribute (e.g. requests.Response)
    - Dicts with a ``"status_code"`` key
    - Anything else returns False (no retry)

    Example:
        RETRYABLE = {429, 500, 502, 503, 504}

        policy = (
            RetryPolicy()
            .attempts(5)
            .retry_if_result(retry_if_status(RETRYABLE))
            .return_result()
        )
    """
    frozen = frozenset(statuses)

    def predicate(response: Any) -> bool:
        if hasattr(response, "status_code"):
            code = response.status_code
            return isinstance(code, int) and code in frozen
        if isinstance(response, dict) and "status_code" in response:
            code = response["status_code"]
            return isinstance(code, int) and code in frozen
        return False

    return predicate


def retry_after_delay(default: float, maximum: float | None = None) -> Callable[[int], float]:
    """
    Return a custom delay callback that always returns a fixed default value.

    This is useful as a starting point when you want a predictable delay for
    HTTP retries without implementing dynamic Retry-After header parsing. The
    delay does not adapt to the response because delay strategies in RetryFlow
    only receive the attempt number, not the last response.

    For dynamic Retry-After support, use the before_sleep event to read the
    header value and coordinate with a custom_delay callback via shared state.

    Args:
        default: The base delay in seconds.
        maximum: Optional upper bound. The returned delay is capped at this value.

    Example:
        policy = (
            RetryPolicy()
            .attempts(5)
            .custom_delay(retry_after_delay(default=1.0, maximum=30.0))
        )
    """

    def delay(_attempt: int) -> float:
        d = default
        if maximum is not None:
            d = min(d, maximum)
        return d

    return delay


def parse_retry_after(header_value: str, default: float = 0.0) -> float:
    """
    Parse a Retry-After header value into a delay in seconds.

    Accepts:
    - An integer string representing seconds (e.g. "120")
    - An HTTP-date string (e.g. "Wed, 04 Jun 2026 12:00:00 GMT")
    - Any unparseable value falls back to default

    Returns:
        The number of seconds to wait. Never returns a negative value.

    Example:
        delay = parse_retry_after(response.headers.get("Retry-After", ""), default=5.0)
    """
    stripped = header_value.strip()

    # Try integer seconds first
    try:
        seconds = int(stripped)
        return max(0.0, float(seconds))
    except ValueError:
        pass

    # Try HTTP date (RFC 2822, e.g. "Wed, 04 Jun 2026 12:00:00 GMT")
    # parsedate_tz + mktime_tz correctly handles the GMT/UTC timezone offset.
    try:
        parsed = parsedate_tz(stripped)
        if parsed is not None:
            target = float(mktime_tz(parsed))
            delay = target - time.time()
            return max(0.0, delay)
    except Exception:  # noqa: BLE001
        pass

    return default
