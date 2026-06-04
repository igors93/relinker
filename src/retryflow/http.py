"""
Dependency-free HTTP helpers for retry policies.

These helpers make it easy to build HTTP-aware retry policies without adding any
runtime dependencies. They work with any HTTP library or custom response object
that exposes a status code or headers.

Idempotency note:
    Retrying HTTP requests is safe for idempotent methods (GET, HEAD, PUT,
    DELETE, OPTIONS). Retrying POST, PATCH, or other non-idempotent methods can
    cause duplicate side effects. RetryFlow does not block non-idempotent retries
    because this is an application-level concern, but the helpers keep the risk
    visible in the documentation.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from email.utils import mktime_tz, parsedate_tz
from typing import TYPE_CHECKING, Any

from retryflow.exceptions import InvalidRetryConfigError
from retryflow.internal.validation import ensure_non_negative, ensure_positive_int
from retryflow.state import RetryState

if TYPE_CHECKING:
    from retryflow.policy import RetryPolicy

DEFAULT_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_MAX_RETRY_AFTER_HEADER_LENGTH = 256


def _normalize_statuses(statuses: Iterable[int]) -> frozenset[int]:
    normalized = frozenset(statuses)

    for status in normalized:
        if not isinstance(status, int) or status < 100 or status > 599:
            raise InvalidRetryConfigError("HTTP status codes must be integers between 100 and 599")

    return normalized


def should_retry_http_status(status_code: int, statuses: Iterable[int]) -> bool:
    """Return True when status_code is in the provided retryable status collection."""
    if not isinstance(status_code, int):
        return False
    return status_code in _normalize_statuses(statuses)


def retry_if_status(statuses: Iterable[int]) -> Callable[[Any], bool]:
    """
    Return a result predicate for use with policy.retry_if_result().

    The predicate returns True (retry) when the response's status code is in the
    given set. Supports objects with a .status_code attribute and dictionaries
    with a "status_code" key.
    """
    frozen = _normalize_statuses(statuses)

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
    Return a state-aware delay callback that honours the Retry-After header.

    The callback reads state.last_value to inspect the response object. When the
    header is absent or unparseable, it returns default. The returned delay is
    never negative and is capped by maximum when provided. Negative defaults are
    normalized to zero so the helper remains safe even with user-provided config.
    """
    safe_default = max(0.0, default)
    if maximum is not None:
        ensure_non_negative("maximum", maximum)

    def delay(state: RetryState) -> float:
        header_value = _extract_retry_after_header(state.last_value)
        if header_value is not None:
            resolved = parse_retry_after(header_value, default=safe_default)
        else:
            resolved = safe_default
        if maximum is not None:
            resolved = min(resolved, maximum)
        return max(0.0, resolved)

    return delay


def http_retry_policy(
    *,
    attempts: int = 5,
    statuses: Iterable[int] = DEFAULT_RETRYABLE_STATUSES,
    default_delay: float = 1.0,
    maximum_delay: float | None = 60.0,
    respect_retry_after: bool = True,
) -> RetryPolicy[Any]:
    """
    Return a ready-to-use HTTP result-based retry policy.

    This recipe retries responses whose status code is in statuses. When
    respect_retry_after=True, it uses a stateful delay that honours Retry-After.
    Otherwise it falls back to exponential backoff.
    """
    ensure_positive_int("attempts", attempts)
    ensure_non_negative("default_delay", default_delay)
    if maximum_delay is not None:
        ensure_non_negative("maximum_delay", maximum_delay)

    from retryflow.policy import RetryPolicy

    policy: RetryPolicy[Any] = (
        RetryPolicy().attempts(attempts).retry_if_result(retry_if_status(statuses))
    )
    if respect_retry_after:
        return policy.stateful_delay(
            retry_after_delay(default=default_delay, maximum=maximum_delay)
        )
    return policy.exponential_delay(base=default_delay, maximum=maximum_delay)


def _extract_retry_after_header(response: Any) -> str | None:
    """Extract the Retry-After header value from a response object."""
    headers: Any = None

    if hasattr(response, "headers"):
        headers = response.headers
    elif isinstance(response, dict) and "headers" in response:
        headers = response["headers"]

    if headers is None or not hasattr(headers, "get"):
        return None

    for name in ("Retry-After", "retry-after", "RETRY-AFTER"):
        value = headers.get(name)
        if value is not None:
            return str(value)

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

    Accepts non-negative integer seconds and HTTP-date strings. Any unparseable
    or unusually large header value falls back to default. Negative defaults are
    normalized to zero so this helper never returns a negative delay.
    """
    safe_default = max(0.0, default)

    stripped = header_value.strip()
    if not stripped or len(stripped) > _MAX_RETRY_AFTER_HEADER_LENGTH:
        return safe_default

    if stripped.isdigit():
        return float(int(stripped))

    try:
        parsed = parsedate_tz(stripped)
        if parsed is not None:
            target = float(mktime_tz(parsed))
            delay = target - time.time()
            return max(0.0, delay)
    except Exception:  # noqa: BLE001
        pass

    return safe_default
