"""Type aliases are defined once and re-exported where they were used before."""

from __future__ import annotations

import relinker.presets
import relinker.typing


def test_exception_types_alias_has_a_single_definition() -> None:
    # tuple[...] aliases are not cached, so a second definition would be a
    # distinct object.
    assert relinker.presets.ExceptionTypes is relinker.typing.ExceptionTypes
