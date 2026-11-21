import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from typer.testing import CliRunner

from friday import cli
from friday.config import Settings
from friday.logging import OperationalEvent, log_event
from friday.safety.privacy import redact


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings.model_validate(
        {
            "provider": "groq",
            "providers": {
                p: {
                    "model": "unit-model",
                    "api_key_env": "CUSTOM",
                    "api_key": "opaque-test-key",
                    "base_url": "https://test.invalid/v1",
                }
                for p in ("groq", "ollama")
            },
            "request": {"retries": 0},
            "logging": {"path": tmp_path / "events"},
            "history": {"path": tmp_path / "database"},
        }
    )
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    return settings


@pytest.mark.parametrize("debug", [True, False])
def test_content_excluded(settings: Settings, monkeypatch: pytest.MonkeyPatch, debug: bool) -> None:
    settings.logging.detailed = debug
    prompt = "My password=super-private and Bearer personal-token"
    answer = "private assistant reply"
    data = {
        "choices": [{"message": {"content": answer}}],
        "usage": {"total_tokens": 12, "unexpected": prompt},
    }
    response = httpx.Response(200, json=data, request=httpx.Request("POST", "https://unit.invalid"))
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)
    result = CliRunner().invoke(cli.app, ["chat", prompt])
    assert result.exit_code == 0
    assert result.stdout.strip() == answer
    body = settings.logging.path.read_text()
    for forbidden in (prompt, answer, "super-private", "personal-token", "opaque-test-key"):
        assert forbidden not in body
    record = json.loads(body)
    assert UUID(record["request_id"]) and record["timestamp"]
    assert record["duration_ms"] >= 0 and record["model"] == "unit-model"
    assert record["status"] == "success" and record["provider"] == "groq"
    assert record["task_category"] == "chat" and record["token_usage"] == {"total_tokens": 12}
    assert ("streaming" in record) == debug
    assert settings.history.path is not None and not settings.history.path.exists()


@pytest.mark.parametrize(("provider", "command"), [("ollama", "repl"), ("groq", "chat")])
def test_provider_errors(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, provider: str, command: str
) -> None:
    settings.provider = provider  # type: ignore[assignment]
    settings.logging.detailed = True
    request_id = uuid4()
    response = httpx.Response(
        401,
        text="secret provider body",
        headers={"x-request-id": str(request_id)},
        request=httpx.Request("POST", "https://unit.invalid/private-url"),
    )
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)

    @contextmanager
    def stream(*args: object, **kwargs: object) -> Iterator[httpx.Response]:
        yield response

    monkeypatch.setattr(httpx, "stream", stream)
    args = ["chat", "private prompt"] if command == "chat" else ["repl"]
    result = CliRunner().invoke(cli.app, args, input="local message\n")
    assert result.exit_code == 1 and "HTTP 401" in result.output
    audit = settings.logging.path.read_text()
    for secret in ("secret provider body", "private-url", "opaque-test-key", "Traceback"):
        assert secret not in result.output + audit
    assert "local message" not in audit and "private prompt" not in audit
    event = json.loads(audit)
    assert event["status"] == "failure" and event["error_category"] == "http"
    assert event["provider_request_id"] == str(request_id)
    assert event["error_code"] == "HTTP_401"


def test_transport_error_and_unknown_header_are_safe(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("private transport detail password=never-print")

    monkeypatch.setattr(httpx, "post", fail)
    result = CliRunner().invoke(cli.app, ["chat", "opaque-test-key"])
    audit = settings.logging.path.read_text()
    assert result.exit_code == 1 and json.loads(audit)["error_code"] == "TRANSPORT"
    assert "never-print" not in result.output + audit
    assert "opaque-test-key" not in result.output + audit
    response = httpx.Response(
        403,
        headers={"x-request-id": "secret-provider-header"},
        request=httpx.Request("POST", "https://unit.invalid"),
    )
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)
    result = CliRunner().invoke(cli.app, ["chat", "test"])
    assert result.exit_code == 1
    assert "secret-provider-header" not in result.output + settings.logging.path.read_text()


def test_history_cannot_share_log_path(settings: Settings) -> None:
    values = settings.model_dump()
    values["history"]["path"] = settings.logging.path
    with pytest.raises(ValueError, match="separate files"):
        Settings.model_validate(values)


def test_redaction_and_debug_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_ACCESS_TOKEN", "inherited-secret")
    samples = [
        "inherited-secret",
        "gsk_abcdefghijk",
        "sk-abcdefghijk",
        "Bearer ey-example",
        "password='abc 123'",
        "access_token=mytoken",
        "-----BEGIN PRIVATE KEY-----\nprivate\n-----END PRIVATE KEY-----",
    ]
    assert all(redact(value) == "[REDACTED]" for value in samples)
    event = OperationalEvent(
        provider="ollama",
        model="inherited-secret",
        tool_name="sk-abcdefghijk",
        duration_ms=1,
        status="success",
        approval_status="approved",
        tool_status="completed",
        streaming=True,
    )
    path = tmp_path / "audit"
    log_event(path, event, detailed=True)
    record = json.loads(path.read_text())
    assert record["model"] == record["tool_name"] == "[REDACTED]"
    assert record["tool_status"] == "completed" and record["approval_status"] == "approved"
    with pytest.raises(ValueError):
        OperationalEvent.model_validate({**record, "payload": {"password": "private"}})
