import relinker


def test_public_version_matches_expected_release() -> None:
    assert relinker.__version__ == "0.8.0"
