"""Shared provider contract."""

from collections.abc import Iterator, Sequence
from typing import Protocol, TypeAlias

Message: TypeAlias = dict[str, str]
ChatOutput: TypeAlias = str | Iterator[str]


class LLMError(RuntimeError):
    """A configuration, transport, or response error from an LLM provider."""


class LLMProvider(Protocol):
    def chat(
        self,
        messages: Sequence[Message],
        tools: list[dict[str, object]] | None = None,
        stream: bool = False,
    ) -> ChatOutput:
        """Send a chat request and return text or a stream of text chunks."""
