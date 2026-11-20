# FRIDAY

FRIDAY is a personal assistant designed around a central orchestrator, specialized modules, persistent memory, evaluation, and explicit safety controls. This repository starts with Milestone 0: text chat through a provider-neutral interface.

## Setup

1. Install Python 3.11+ and `uv`.
2. Run `uv sync --dev`.
3. Copy `.env.example` to `.env` and add `GROQ_API_KEY` if using Groq.
4. Set `provider` and its exact `model` in `config.yaml`. For Ollama, check the installed identifiers with `ollama list`.
5. Run `uv run friday chat "Hello"` or `uv run friday repl`.

Groq and Ollama use the same OpenAI-compatible chat interface. Set `provider: groq` or `provider: ollama` in `config.yaml` to switch. Ollama defaults to `http://localhost:11434/v1` and does not require a secret in a standard local setup.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the initial design and [docs/PROGRESS.md](docs/PROGRESS.md) for milestone status.
