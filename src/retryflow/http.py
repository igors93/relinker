"""
Dependency-free HTTP helpers for retry policies.

These helpers make it easy to build HTTP-aware retry policies without adding
any runtime dependencies. They work with any HTTP library or custom response
object that exposes a status code or headers.

Idempotency note:
    Retrying HTTP requests is safe for idempotent methods (GET, HEAD, PUT,
    DELETE, OPTIONS). Retrying POST, PATCH, or other non-idempotent methods
    can cause duplicate side effects. RetryFlow does not block non-idempotent
    retries — this is an application-level concern — but this module documents
    the concern so users can decide.

Retry-After note:
    retry_after_delay() is designed for use with policy.stateful_delay(). It
    reads state.last_value to inspect the response object. This requires a
    result-based retry condition (retry_if_result) so the response is available
    in the state before each sleep.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from email.utils import mktime_tz, parsedate_tz
from typing import Any

from retryflow.state import RetryState


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
            .stateful_delay(retry_after_delay(default=1.0))
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


def retry_after_delay(
    default: float,
    maximum: float | None = None,
) -> Callable[[RetryState], float]:
    """
    Return a state-aware delay callback that honours the Retry-After response header.

    This callback is designed for use with policy.stateful_delay(). It reads
    state.last_value to find a response object and inspects its Retry-After header.
    When the header is absent or unparseable, it returns the default value.

    The response is available in state.last_value when you use retry_if_result() —
    the executor stores the most recent returned value in the state before sleep.

    Supports:
    - Objects with a ``.headers`` mapping attribute (case-insensitive lookup when possible)
    - Dicts with a ``"headers"`` key containing a mapping
    - Any other response type falls back to the default delay

    Header formats supported:
    - Integer seconds: ``Retry-After: 120``
    - HTTP date:       ``Retry-After: Wed, 04 Jun 2026 12:00:00 GMT``

    Args:
        default: Delay in seconds when no valid Retry-After header is found.
        maximum: Optional cap. The returned delay is never greater than this.

    Example:
        from retryflow.http import retry_if_status, retry_after_delay

        RETRYABLE = {429, 500, 502, 503, 504}

        policy = (
            RetryPolicy()
            .attempts(5)
            .retry_if_result(retry_if_status(RETRYABLE))
            .stateful_delay(retry_after_delay(default=1.0, maximum=60.0))
        )
    """

    def delay(state: RetryState) -> float:
        header_value = _extract_retry_after_header(state.last_value)
        if header_value is not None:
            d = parse_retry_after(header_value, default=default)
        else:
            d = default
        if maximum is not None:
            d = min(d, maximum)
        return max(0.0, d)

    return delay


def _extract_retry_after_header(response: Any) -> str | None:
    """Extract the Retry-After header value from a response object."""
    headers: Any = None

    if hasattr(response, "headers"):
        headers = response.headers
    elif isinstance(response, dict) and "headers" in response:
        headers = response["headers"]

    if headers is None:
        return None

    if not hasattr(headers, "get"):
        return None

    # Try exact case first, then lowercase, then case-insensitive scan
    for name in ("Retry-After", "retry-after", "RETRY-AFTER"):
        value = headers.get(name)
        if value is not None:
            return str(value)

    # Fall back to a full case-insensitive scan for unusual header casings
    try:
        for key in headers:
            if isinstance(key, str) and key.lower() == "retry-after":
                value = headers[key]
                if value is not None:
                    return str(value)
    except Exception:  # noqa: BLE001
        pass

    return None


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
