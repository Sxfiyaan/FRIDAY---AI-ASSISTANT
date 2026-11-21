# FRIDAY Project Rules

- Use Python 3.11, `uv`, Pydantic, pytest, and Ruff. Add type hints everywhere.
- Never hardcode model names, API keys, or paths. Read them from `config.yaml` and `.env`.
- Use one central orchestrator with specialized tools and agents. Keep source files under 300 lines.
- Every tool must define a Pydantic schema, a risk level (`READ`, `WRITE`, `DESTRUCTIVE`, or `NEVER`), and tests.
- Each milestone ends with passing tests, an update to `docs/PROGRESS.md`, and a commit.
- Financial trades are NEVER executed autonomously.
- Keep secrets out of source control. `.env` is local-only; commit `.env.example` instead.

## Project memory

- Multi-model routing is required. One central orchestrator coordinates Groq GPT-OSS 20B for text reasoning and local Ollama Qwen 3.5 9B for vision. Screenshot debugging passes privacy-permitted text findings from Qwen to GPT-OSS. All tool actions go through validation and the permission engine.
- Review the specifications in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before starting Milestone 1. Track approval and milestone status in [docs/PROGRESS.md](docs/PROGRESS.md).
