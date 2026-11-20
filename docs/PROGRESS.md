# FRIDAY Progress

## Milestone 0: Foundation

Status: implementation complete; automated checks pass. Live-provider verification remains.

- Added project rules and architecture documentation.
- Added YAML plus `.env` settings for Groq and Ollama.
- Added a shared OpenAI-compatible chat provider with bounded timeouts/retries and streaming.
- Added `friday chat` and `friday repl` commands with JSONL activity logging.
- Added offline fake-provider and config environment-override tests; `pytest` passes (3 tests).
- Ruff passes (`uv run ruff check .`).
- Set Ollama as the default provider with the configured local model `qwen3.5:9b`.
- Configured Groq model `openai/gpt-oss-120b`, listed as a production model in [Groq's model docs](https://console.groq.com/docs/models). Add `GROQ_API_KEY` to local `.env` before selecting Groq.
- A real-provider smoke test still requires a running Ollama server or valid Groq credentials and is not part of the offline test suite.
- Milestone commit: pending.
