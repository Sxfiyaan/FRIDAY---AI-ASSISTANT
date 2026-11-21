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

## Chat privacy

By default the REPL remembers earlier turns in the current session and discards them on exit. Operational events go to `logs/events.jsonl`. They include a request ID, model, duration, outcome and available token counts. Set `logging.detailed: true` in `config.yaml` to additionally record the streaming flag. Set it back to `false` to disable detailed mode. Both modes exclude conversation text, payloads and raw provider errors.

### Enable encrypted conversation history

1. Generate an independent Fernet key for each local user. In PowerShell, the following command sets a fresh key for the current shell without displaying it. Run it once per new identity. To access that history later, preserve the same value in a private credential store or your local `.env` as `FRIDAY_HISTORY_KEY`.

   ```powershell
   $env:FRIDAY_HISTORY_KEY = py -m uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. Set `history.enabled: true` and choose `history.retention_days` in `config.yaml`. The default is 30 days per turn. Restart FRIDAY. Successful turns are encrypted before SQLite receives them. The history key controls who can read and delete them. Anyone with a copy of the key and database can read that user's history. Keep the database directory and key private to the OS user, including on Windows.
3. Run `py -m uv run friday history list` to find your conversation ID. Use `history show ID` to read it or `history delete ID` to delete it. These commands still work with the original key after saving is disabled. Expired turns are purged on the next history operation. An idle database can retain encrypted expired rows until then.

When upgrading, exit any already-running REPL with `/exit` and start a new one. Earlier versions wrote complete turns to `logs/friday.jsonl`. Treat that file and its backups as private. Delete them separately if you no longer need them. History deletion applies to the application database.
