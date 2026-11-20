"""OpenAI-compatible chat completions client for hosted or local providers."""

import json
import time
from collections.abc import Iterator, Sequence

import httpx

from friday.config import ProviderSettings, RequestSettings
from friday.llm.base import ChatOutput, LLMError, Message


class OpenAICompatibleProvider:
    def __init__(self, provider: ProviderSettings, request: RequestSettings) -> None:
        if not provider.model.strip():
            raise LLMError("Set the selected provider's model in config.yaml.")
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
        headers = {"Authorization": f"Bearer {self.provider.api_key or ''}"}
        endpoint = f"{self.provider.base_url.rstrip('/')}/chat/completions"
        if stream:
            return self._stream(endpoint, headers, payload)
        for attempt in range(self.request.retries + 1):
            try:
                response = httpx.post(
                    endpoint, headers=headers, json=payload,
                    timeout=self.request.timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
                return str(data["choices"][0]["message"].get("content") or "")
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                if attempt >= self.request.retries:
                    raise LLMError(self._message(exc)) from exc
                time.sleep(min(0.5 * (2**attempt), 4))
        raise LLMError("Request failed unexpectedly.")

    def _stream(
        self, endpoint: str, headers: dict[str, str], payload: dict[str, object]
    ) -> Iterator[str]:
        def chunks() -> Iterator[str]:
            for attempt in range(self.request.retries + 1):
                try:
                    with httpx.stream(
                        "POST", endpoint, headers=headers, json=payload,
                        timeout=self.request.timeout_seconds,
                    ) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if not line.startswith("data:"):
                                continue
                            item = line[5:].strip()
                            if item == "[DONE]":
                                return
                            try:
                                parsed = json.loads(item)
                                content = parsed["choices"][0]["delta"].get("content")
                            except (KeyError, IndexError, ValueError) as exc:
                                raise LLMError("Provider returned an invalid stream chunk.") from exc
                            if content:
                                yield str(content)
                    return
                except httpx.HTTPError as exc:
                    if attempt >= self.request.retries:
                        raise LLMError(self._message(exc)) from exc
                    time.sleep(min(0.5 * (2**attempt), 4))
        return chunks()

    @staticmethod
    def _message(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            return f"LLM request failed ({exc.response.status_code}): {exc.response.text[:500]}"
        return f"LLM request failed: {exc}"
