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

### Privacy implementation

- Replaced transcript logging with typed metadata events for success and failure. Detailed mode adds only the streaming flag. The Groq/Ollama client now reports safe errors, and the CLI suppresses raw exception details.
- Added opt-in, key-scoped encrypted SQLite history with configurable retention and CLI commands to list, show and delete conversations. Existing plaintext logs require separate handling. See the [operator instructions](../README.md#chat-privacy).
- Automated checks cover both chat entry points, secret redaction, safe provider errors, request metadata, debug mode, in-session context, encrypted history, access control, expiry and deletion.
- Verification passed with 12 pytest cases and Ruff. A live streaming turn with local Ollama returned an answer and produced an operational event with token counts. Groq error handling was verified offline.
