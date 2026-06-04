import json

from retryflow import RetryPolicy


def test_retry_result_to_dict_excludes_value_by_default() -> None:
    result = RetryPolicy().attempts(1).return_result().run(lambda: {"secret": "value"})

    data = result.to_dict()

    assert data["succeeded"] is True
    assert data["attempt_count"] == 1
    assert "value" not in data


def test_retry_result_to_dict_can_include_value() -> None:
    result = RetryPolicy().attempts(1).return_result().run(lambda: "ok")

    data = result.to_dict(include_value=True)

    assert data["value"] == "ok"


def test_retry_result_to_json() -> None:
    result = RetryPolicy().attempts(1).return_result().run(lambda: "ok")

    data = json.loads(result.to_json())

    assert data["succeeded"] is True
    assert data["attempt_count"] == 1
