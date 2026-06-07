from __future__ import annotations

import relinker
import relinker.result_conditions as result_conditions

EXPECTED_RESULT_CONDITIONS_API = (
    "retry_if_empty",
    "retry_if_false",
    "retry_if_none",
    "retry_if_value",
)


def test_result_conditions_public_api_matches_snapshot() -> None:
    assert tuple(result_conditions.__all__) == EXPECTED_RESULT_CONDITIONS_API


def test_result_conditions_helpers_are_not_root_exports() -> None:
    for name in EXPECTED_RESULT_CONDITIONS_API:
        assert name not in relinker.__all__


def test_every_result_conditions_export_exists() -> None:
    missing = [
        name for name in EXPECTED_RESULT_CONDITIONS_API if not hasattr(result_conditions, name)
    ]

    assert missing == []
