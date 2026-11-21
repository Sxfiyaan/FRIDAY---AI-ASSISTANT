"""Load typed application settings from YAML and local environment."""

import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator


class ProviderSettings(BaseModel):
    base_url: str
    model: str
    api_key_env: str
    api_key: str | None = None


class RequestSettings(BaseModel):
    timeout_seconds: float = Field(default=60, gt=0)
    retries: int = Field(default=2, ge=0, le=10)


class LoggingSettings(BaseModel):
    path: Path = Path("logs/friday.jsonl")
    detailed: bool = False


class HistorySettings(BaseModel):
    enabled: bool = False
    path: Path | None = None
    key_env: str = "FRIDAY_HISTORY_KEY"
    retention_days: int = Field(default=30, ge=1, le=36500)


class Settings(BaseModel):
    provider: Literal["groq", "ollama"]
    providers: dict[str, ProviderSettings]
    request: RequestSettings = RequestSettings()
    logging: LoggingSettings = LoggingSettings()
    history: HistorySettings = HistorySettings()

    @model_validator(mode="after")
    def distinct_storage_paths(self) -> "Settings":
        if self.history.path and self.history.path.resolve() == self.logging.path.resolve():
            raise ValueError("History and operational logs require separate files.")
        return self

    def selected_provider(self) -> ProviderSettings:
        return self.providers[self.provider]


def load_settings(path: Path | None = None) -> Settings:
    """Read config.yaml and .env, with environment values taking precedence."""
    load_dotenv()
    path = path or Path(os.getenv("FRIDAY_CONFIG", "config.yaml"))
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for provider in raw.get("providers", {}).values():
        env_name = provider.get("api_key_env", "")
        if env_name:
            env_value = os.getenv(env_name)
            if env_value:
                provider["api_key"] = env_value
    return Settings.model_validate(raw)
