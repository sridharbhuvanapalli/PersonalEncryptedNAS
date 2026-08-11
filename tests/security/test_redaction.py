from pnas.security import redact


def test_secret_fields_and_bearer_values_are_redacted() -> None:
    value = redact(
        {"api_token": "super-secret", "message": "Authorization: Bearer abc.def.ghi", "ok": 1}
    )
    assert value["api_token"] == "[REDACTED]"  # noqa: S105
    assert "abc.def.ghi" not in value["message"]
    assert value["ok"] == 1
