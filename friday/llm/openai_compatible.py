"""OpenAI-compatible chat client with payload-free errors and usage reporting."""

import json
import time
from collections.abc import Iterator, Sequence
from typing import Any

import httpx
from pydantic import ValidationError

from friday.config import ProviderSettings, RequestSettings
from friday.llm.base import ChatOutput, LLMError, Message
from friday.logging import TokenUsage, usage
from friday.safety.privacy import provider_error

_PROVIDER_FAILURES = (
    httpx.HTTPError,
    httpx.InvalidURL,
    ValueError,
    TypeError,
    LookupError,
    AttributeError,
    UnicodeError,
)


def record_usage(data: dict[str, Any]) -> None:
    if isinstance(data.get("usage"), dict):
        try:
            usage.set(TokenUsage.model_validate(data["usage"]))
        except ValidationError:
            pass  # Malformed optional metadata must not leak data or discard a valid answer.


class OpenAICompatibleProvider:
    def __init__(self, provider: ProviderSettings, request: RequestSettings) -> None:
        if not provider.model.strip():
            raise LLMError("configuration")
        self.provider = provider
        self.request = request

    def chat(
        self,
        messages: Sequence[Message],
        tools: list[dict[str, object]] | None = None,
        stream: bool = False,
    ) -> ChatOutput:
        payload: dict[str, object] = {
            "model": self.provider.model,
            "messages": list(messages),
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
        headers = (
            {"Authorization": f"Bearer {self.provider.api_key}"} if self.provider.api_key else {}
        )
        endpoint = f"{self.provider.base_url.rstrip('/')}/chat/completions"
        if stream:
            payload["stream_options"] = {"include_usage": True}
            return self._stream(endpoint, headers, payload)
        for attempt in range(self.request.retries + 1):
            try:
                response = httpx.post(
                    endpoint, headers=headers, json=payload, timeout=self.request.timeout_seconds
                )
                response.raise_for_status()
                data = response.json()
                record_usage(data)
                content = data["choices"][0]["message"].get("content")
                if content is None:
                    return ""
                if not isinstance(content, str):
                    raise TypeError
                return content
            except _PROVIDER_FAILURES as exc:
                self._retry(exc, attempt)
        raise LLMError("transport")

    def _retry(self, exc: Exception, attempt: int, *, emitted: bool = False) -> None:
        transient = isinstance(exc, httpx.TransportError) or (
            isinstance(exc, httpx.HTTPStatusError)
            and (exc.response.status_code == 429 or exc.response.status_code >= 500)
        )
        if emitted or attempt >= self.request.retries or not transient:
            raise provider_error(exc) from None
        time.sleep(min(0.5 * (2**attempt), 4))

    def _stream(
        self, endpoint: str, headers: dict[str, str], payload: dict[str, object]
    ) -> Iterator[str]:
        emitted = False
        for attempt in range(self.request.retries + 1):
            try:
                with httpx.stream(
                    "POST",
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.request.timeout_seconds,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        item = line[5:].strip()
                        if item == "[DONE]":
                            return
                        data = json.loads(item)
                        record_usage(data)
                        if data.get("choices") == [] and "usage" in data:
                            continue
                        content = data["choices"][0]["delta"].get("content")
                        if content is not None and not isinstance(content, str):
                            raise TypeError
                        if content:
                            emitted = True
                            yield content
                return
            except _PROVIDER_FAILURES as exc:
                self._retry(exc, attempt, emitted=emitted)
