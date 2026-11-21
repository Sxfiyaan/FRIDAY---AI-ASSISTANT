"""Boundaries for diagnostic data shared by the CLI, providers and audit log."""

import os
import re
from collections.abc import Iterable
from typing import Literal, get_args
from uuid import UUID

import httpx

_SECRET_NAME = re.compile(
    r"key|password|passwd|secret|token|credential|authorization", re.IGNORECASE
)
_PATTERNS = (
    re.compile(
        r"-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|\Z)", re.DOTALL
    ),
    re.compile(r"\b(?:gsk_|sk-|gh[pousr]_)[A-Za-z0-9_-]{6,}"),
    re.compile(r"\b(?:Bearer|Basic)\s+[^\s,;'\"}]+", re.IGNORECASE),
    re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+"),
    re.compile(r"(?<=://)[^/\s@]+:[^/\s@]+@"),
    re.compile(r"""(?ix)["']?[\w.-]*(?:password|passwd|api[_-]?key|token|secret|credential)
               ["']?\s*[:=]\s*(?:"[^"]*"|'[^']*'|[^\s,;}]+)"""),
)


def redact(value: str, secrets: Iterable[str] = ()) -> str:
    """Remove known secret values as well as common credential formats."""
    known = {v for k, v in os.environ.items() if v and _SECRET_NAME.search(k)}
    known.update(s for s in secrets if s)
    for secret in sorted(known, key=len, reverse=True):
        value = value.replace(secret, "[REDACTED]")
    for pattern in _PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


Category = Literal[
    "configuration", "timeout", "transport", "http", "response", "storage", "internal"
]


class SafeError(RuntimeError):
    def __init__(
        self, category: Category, status: int | None = None, provider_request_id: UUID | None = None
    ) -> None:
        self.category: Category = category if category in get_args(Category) else "internal"
        self.status = status if type(status) is int and 100 <= status <= 599 else None
        self.provider_request_id = provider_request_id
        code = f" (HTTP {self.status})" if self.status is not None else ""
        super().__init__(f"FRIDAY {self.category} error{code}.")


def provider_error(exc: Exception) -> SafeError:
    if isinstance(exc, httpx.HTTPStatusError):
        header = exc.response.headers.get("x-request-id", "")
        try:
            request_id = UUID(header)
        except ValueError:
            request_id = None
        return SafeError("http", exc.response.status_code, request_id)
    if isinstance(exc, httpx.TimeoutException):
        return SafeError("timeout")
    if isinstance(exc, (httpx.HTTPError, httpx.InvalidURL)):
        return SafeError("transport")
    return SafeError("response")
