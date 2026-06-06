"""Public API export contracts for Relinker."""

from __future__ import annotations

import relinker
import relinker.context as context

EXPECTED_ROOT_PUBLIC_API = (
    "AsyncRetryAttemptContext",
    "DEFAULT_RETRYABLE_STATUSES",
    "MAX_RETRY_AFTER_SECONDS",
    "InvalidRetryConfigError",
    "PolicyHealthReport",
    "PolicyWarning",
    "RetryAttemptContext",
    "RetryBudget",
    "RetryExhaustedError",
    "RelinkerError",
    "RetryPolicy",
    "RetryResult",
    "RetrySimulation",
    "RetrySimulationAttempt",
    "RetryState",
    "RetryStats",
    "RetryStatsSnapshot",
    "RetryWrappedFunction",
    "TryAgain",
    "background_job",
    "database",
    "fast",
    "http_retry_policy",
    "network",
    "parse_retry_after",
    "patient",
    "retry",
    "retry_after_delay",
    "retry_if_status",
    "should_retry_http_status",
)

EXPECTED_CONTEXT_PUBLIC_API = (
    "AsyncRetryAttemptContext",
    "AsyncRetryBlockIterator",
    "RetryAttemptContext",
    "RetryBlockIterator",
)


def test_root_public_api_matches_snapshot() -> None:
    assert tuple(relinker.__all__) == EXPECTED_ROOT_PUBLIC_API


def test_every_root_public_export_exists() -> None:
    missing = [name for name in EXPECTED_ROOT_PUBLIC_API if not hasattr(relinker, name)]

    assert missing == []


def test_root_public_api_has_no_duplicate_names() -> None:
    assert len(relinker.__all__) == len(set(relinker.__all__))


def test_version_is_available_but_not_part_of_star_import_api() -> None:
    assert isinstance(relinker.__version__, str)
    assert relinker.__version__
    assert "__version__" not in relinker.__all__


def test_internal_runtime_symbols_are_not_root_exports() -> None:
    forbidden_exports = {
        "RetryRuntime",
        "RetryWaitPlan",
        "_RetryReservation",
        "_BaseRetryAttemptContext",
        "_BaseRetryBlockIterator",
    }

    assert forbidden_exports.isdisjoint(relinker.__all__)


def test_context_public_api_matches_snapshot() -> None:
    assert tuple(context.__all__) == EXPECTED_CONTEXT_PUBLIC_API


def test_every_context_public_export_exists() -> None:
    missing = [name for name in EXPECTED_CONTEXT_PUBLIC_API if not hasattr(context, name)]

    assert missing == []


def test_root_public_objects_are_resolvable() -> None:
    for name in EXPECTED_ROOT_PUBLIC_API:
        assert getattr(relinker, name) is not None
