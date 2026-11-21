import time
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from typer.testing import CliRunner

from friday import cli
from friday.config import HistorySettings, Settings
from friday.memory.conversations import Conversations
from friday.safety.privacy import SafeError


def test_history_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "store"
    settings = Settings.model_validate(
        {
            "provider": "ollama",
            "providers": {"ollama": {"model": "test", "base_url": "local", "api_key_env": "TEST"}},
            "history": {"enabled": True, "path": db},
            "logging": {"path": tmp_path / "audit"},
        }
    )
    monkeypatch.setenv(settings.history.key_env, Fernet.generate_key().decode())
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    seen: list[list[str]] = []

    class Provider:
        def chat(self, messages: list[dict[str, str]], stream: bool) -> Iterator[str]:
            seen.append([m["content"] for m in messages])
            return iter(["private reply"])

    monkeypatch.setattr(cli, "make_provider", lambda _: Provider())
    runner = CliRunner()
    result = runner.invoke(cli.app, ["repl"], input="first secret\nsecond secret\n/exit\n")
    assert result.exit_code == 0
    assert seen == [["first secret"], ["first secret", "private reply", "second secret"]]
    identifier = runner.invoke(cli.app, ["history", "list"]).stdout.strip()
    assert UUID(identifier)
    result = runner.invoke(cli.app, ["history", "show", identifier])
    assert result.exit_code == 0 and result.stdout.count("private reply") == 2
    for source in (db, settings.logging.path):
        assert b"first secret" not in source.read_bytes()
        assert b"private reply" not in source.read_bytes()

    original = Conversations(settings.history)
    monkeypatch.setenv(settings.history.key_env, Fernet.generate_key().decode())
    assert runner.invoke(cli.app, ["history", "list"]).stdout == ""
    assert runner.invoke(cli.app, ["history", "show", identifier]).exit_code == 1
    assert runner.invoke(cli.app, ["history", "delete", identifier]).exit_code == 1
    assert len(original.read(UUID(identifier))) == 4

    monkeypatch.setattr(cli, "Conversations", lambda _: original)
    settings.history.enabled = False
    assert runner.invoke(cli.app, ["history", "delete", identifier]).exit_code == 0
    assert runner.invoke(cli.app, ["history", "list"]).stdout == ""


def test_history_retention_and_missing_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = HistorySettings(path=tmp_path / "db", enabled=True, retention_days=1)
    monkeypatch.delenv(settings.key_env, raising=False)
    with pytest.raises(SafeError):
        Conversations(settings)
    assert settings.path is not None and not settings.path.exists()
    monkeypatch.setenv(settings.key_env, Fernet.generate_key().decode())
    store = Conversations(settings)
    first, second = uuid4(), uuid4()
    now = int(time.time())
    store.append(first, "old", "old")
    monkeypatch.setattr(time, "time", lambda: now + 86401)
    store.append(second, "new", "new")
    assert store.list_ids() == [second] and store.read(first) == []
