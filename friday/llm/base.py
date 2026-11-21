"""Shared provider contract."""

from collections.abc import Iterator, Sequence
from typing import Protocol, TypeAlias

from friday.safety.privacy import SafeError

Message: TypeAlias = dict[str, str]
ChatOutput: TypeAlias = str | Iterator[str]


LLMError = SafeError


class LLMProvider(Protocol):
    def chat(
        self,
        messages: Sequence[Message],
        tools: list[dict[str, object]] | None = None,
        stream: bool = False,
    ) -> ChatOutput:
        """Send a chat request and return text or a stream of text chunks."""
