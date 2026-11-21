"""Typed operational events. There is no free-form message or payload field."""

import json
import re
from collections.abc import Iterable
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from friday.safety.privacy import Category, redact


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    prompt_tokens: int | None = Field(None, ge=0)
    completion_tokens: int | None = Field(None, ge=0)
    total_tokens: int | None = Field(None, ge=0)


usage: ContextVar[TokenUsage | None] = ContextVar("usage", default=None)


class OperationalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider: Literal["groq", "ollama"]
    model: str
    task_category: Literal["chat", "tool"] = "chat"
    duration_ms: int = Field(ge=0)
    status: Literal["success", "failure"]
    token_usage: TokenUsage | None = None
    error_category: Category | None = None
    http_status: int | None = Field(None, ge=100, le=599)
    provider_request_id: UUID | None = None
    tool_name: str | None = None
    tool_status: Literal["started", "completed", "failed", "denied"] | None = None
    approval_status: Literal["pending", "approved", "denied"] | None = None
    streaming: bool | None = None


def log_event(
    path: Path, event: OperationalEvent, *, detailed: bool = False, secrets: Iterable[str] = ()
) -> None:
    record = event.model_dump(
        mode="json", exclude_none=True, include=set(OperationalEvent.model_fields)
    )
    known_secrets = tuple(secrets)
    if event.error_category:
        record["error_code"] = (
            f"HTTP_{event.http_status}" if event.http_status else event.error_category.upper()
        )
    if not detailed:
        record.pop("streaming", None)
    for name in ("model", "tool_name", "provider_request_id"):
        if name in record:
            label = redact(record[name], known_secrets)
            record[name] = label if re.fullmatch(r"[\w./:@-]{1,128}", label) else "[REDACTED]"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")
