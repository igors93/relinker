import retryflow


def test_public_version_matches_expected_release() -> None:
    assert retryflow.__version__ == "0.4.0"
