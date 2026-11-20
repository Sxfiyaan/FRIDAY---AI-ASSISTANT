# FRIDAY Project Rules

- Use Python 3.11, `uv`, Pydantic, pytest, and Ruff. Add type hints everywhere.
- Never hardcode model names, API keys, or paths. Read them from `config.yaml` and `.env`.
- Use one central orchestrator with specialized tools and agents. Keep source files under 300 lines.
- Every tool must define a Pydantic schema, a risk level (`READ`, `WRITE`, `DESTRUCTIVE`, or `NEVER`), and tests.
- Each milestone ends with passing tests, an update to `docs/PROGRESS.md`, and a commit.
- Financial trades are NEVER executed autonomously.
- Keep secrets out of source control. `.env` is local-only; commit `.env.example` instead.
