# FRIDAY Progress

## Architecture review and milestone roadmap

**2026-11-21 — Multi-model routing is a required architectural change.** The [updated specification](ARCHITECTURE.md) covers product requirements, the architecture diagram, model strategy, provider and routing contracts, permission checks and eight acceptance tests.

| Stage | Status and deliverable |
| --- | --- |
| Milestone 0 foundation | Committed as `84a87ed`. One-shot and streaming chat verified with the current local Ollama model, `qwen3.5:4b`. Live Groq verification remains open. |
| Pre-Milestone 1 review | Specification ready for user review. The target pairs Groq `openai/gpt-oss-20b` for text reasoning with local Ollama `qwen3.5:9b` for vision. Review the routing rules, privacy-aware handoff, overrides, failure behavior and acceptance criteria before implementation. |
| Milestone 1 | Awaiting specification review and approval. Planned work covers provider adapters, capability-aware selection, orchestrator handoffs, user-visible routing decisions and the specified tests. |

The routing change has been documented only. The Milestone 0 entries below record earlier work.

## Milestone 0: Foundation

**Foundation complete.** Automated checks pass. The security review identified open findings below.

- Added project rules and architecture documentation.
- Added YAML plus `.env` settings for Groq and Ollama.
- Added a shared OpenAI-compatible chat provider with bounded timeouts/retries and streaming.
- Added `friday chat` and `friday repl` commands with JSONL activity logging.
- Added offline fake-provider and config environment-override tests; `pytest` passes (3 tests).
- Ruff passes (`uv run ruff check .`).
- Verified the foundation commit in Git history (`84a87ed`).

### Verification and security review

- All three automated tests and Ruff passed. A separate simulated timeout check confirmed the configured timeout and retry limit and the final provider error.
- Live Ollama one-shot chat and the streaming REPL both returned a reply using `qwen3.5:4b`. Groq configuration has offline test coverage only in this review.
- Git ignores the local `.env` and JSONL logs. Neither is tracked. A limited common-secret-pattern scan found no matches in tracked working-tree files.
- The original review found complete chat turns in the JSONL log and raw upstream error text in the terminal. The privacy implementation below addresses both findings for new sessions.
- The locked-dependency scan flagged pytest 8.4.2, a development dependency, for a Unix temporary-directory issue. The advisory lists 9.0.3 as fixed, outside the current pytest version constraint. [PYSEC-2026-1845](https://osv.dev/vulnerability/PYSEC-2026-1845)

### Privacy implementation

- Replaced transcript logging with typed metadata events for success and failure. Detailed mode adds only the streaming flag. The Groq/Ollama client now reports safe errors, and the CLI suppresses raw exception details.
- Added opt-in, key-scoped encrypted SQLite history with configurable retention and CLI commands to list, show and delete conversations. Existing plaintext logs require separate handling. See the [operator instructions](../README.md#chat-privacy).
- Automated checks cover both chat entry points, secret redaction, safe provider errors, request metadata, debug mode, in-session context, encrypted history, access control, expiry and deletion.
- Verification passed with 12 pytest cases and Ruff. A live streaming turn with local Ollama returned an answer and produced an operational event with token counts. Groq error handling was verified offline.
