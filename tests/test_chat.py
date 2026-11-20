from collections.abc import Sequence
from pathlib import Path

import pytest
import yaml

from friday.cli import reply
from friday.config import load_settings
from friday.llm.base import ChatOutput, Message


class FakeProvider:
    def chat(
        self,
        messages: Sequence[Message],
        tools: list[dict[str, object]] | None = None,
        stream: bool = False,
    ) -> ChatOutput:
        assert messages[-1]["content"] == "hello"
        if stream:
            return iter(["hi", " there"])
        return "hi there"


def test_fake_provider_non_streaming(capsys: pytest.CaptureFixture[str]) -> None:
    assert reply(FakeProvider(), [{"role": "user", "content": "hello"}], False) == "hi there"
    assert capsys.readouterr().out == "hi there\n"


def test_fake_provider_streaming(capsys: pytest.CaptureFixture[str]) -> None:
    result = reply(FakeProvider(), [{"role": "user", "content": "hello"}], True)
    assert result == "hi there"
    assert capsys.readouterr().out == "hi there\n"


def test_config_reads_selected_provider_and_env_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = {
        "provider": "groq",
        "providers": {
            "groq": {
                "base_url": "https://example.invalid/v1",
                "model": "test-model",
                "api_key_env": "TEST_GROQ_KEY",
            },
            "ollama": {
                "base_url": "http://localhost:11434/v1",
                "model": "local-model",
                "api_key_env": "TEST_OLLAMA_KEY",
            },
        },
    }
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setenv("TEST_GROQ_KEY", "test-secret")

    settings = load_settings(config_path)

    assert settings.provider == "groq"
    assert settings.selected_provider().model == "test-model"
    assert settings.selected_provider().api_key == "test-secret"
