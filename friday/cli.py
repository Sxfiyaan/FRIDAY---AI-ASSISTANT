"""Typer commands for chat and private conversation history."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from time import monotonic
from uuid import UUID, uuid4

import typer
from cryptography.fernet import InvalidToken

from friday.config import Settings, load_settings
from friday.llm import LLMError, LLMProvider, OpenAICompatibleProvider
from friday.llm.base import Message
from friday.logging import OperationalEvent, log_event, usage
from friday.memory.conversations import Conversations
from friday.safety.privacy import SafeError

app = typer.Typer(help="FRIDAY personal assistant", pretty_exceptions_enable=False)
history = typer.Typer(help="Manage conversations accessible with your local history key.")
app.add_typer(history, name="history")


@contextmanager
def cli_errors() -> Iterator[None]:
    try:
        yield
    except Exception as exc:
        if isinstance(exc, (typer.Abort, typer.Exit)):
            raise
        if isinstance(exc, SafeError):
            message = str(exc)
        elif isinstance(exc, InvalidToken):
            message = "FRIDAY could not decrypt this conversation."
        else:
            message = "FRIDAY could not complete the operation. Check configuration and storage."
        typer.echo(message, err=True)
        raise typer.Exit(code=1) from None


def make_provider(settings: Settings) -> LLMProvider:
    provider = settings.selected_provider()
    if settings.provider == "groq" and not provider.api_key:
        raise LLMError("configuration")
    return OpenAICompatibleProvider(provider, settings.request)


def reply(provider: LLMProvider, messages: list[Message], stream: bool) -> str:
    output = provider.chat(messages, stream=stream)
    if isinstance(output, str):
        typer.echo(output)
        return output
    chunks: list[str] = []
    for chunk in output:
        typer.echo(chunk, nl=False)
        chunks.append(chunk)
    typer.echo()
    return "".join(chunks)


def chat_turn(settings: Settings, conversation: UUID, messages: list[Message], stream: bool) -> str:
    start = monotonic()
    request_id = uuid4()
    token = usage.set(None)
    error: SafeError | None = None
    try:
        store = Conversations(settings.history) if settings.history.enabled else None
        answer = reply(make_provider(settings), messages, stream)
        if store is not None:
            try:
                store.append(conversation, messages[-1]["content"], answer)
            except (sqlite3.Error, OSError, ValueError):
                raise SafeError("storage") from None
        return answer
    except Exception as exc:  # noqa: BLE001 - audit failures without serializing exception data
        error = exc if isinstance(exc, SafeError) else SafeError("internal")
        raise error from None
    finally:
        counts = usage.get()
        usage.reset(token)
        provider = settings.providers.get(settings.provider)
        event = OperationalEvent(
            request_id=request_id,
            provider=settings.provider,
            model=provider.model if provider else "unknown",
            duration_ms=int((monotonic() - start) * 1000),
            status="failure" if error else "success",
            error_category=error.category if error else None,
            http_status=error.status if error else None,
            provider_request_id=error.provider_request_id if error else None,
            token_usage=counts,
            streaming=stream,
        )
        log_event(
            settings.logging.path,
            event,
            detailed=settings.logging.detailed,
            secrets=[p.api_key for p in settings.providers.values() if p.api_key],
        )


@app.command()
def chat(text: str = typer.Argument(..., help="Message to send to FRIDAY")) -> None:
    """Send a single message."""
    with cli_errors():
        chat_turn(load_settings(), uuid4(), [{"role": "user", "content": text}], False)


@app.command()
def repl() -> None:
    """Start an interactive streaming chat session."""
    with cli_errors():
        settings = load_settings()
        conversation = uuid4()
        messages: list[Message] = []
        typer.echo("FRIDAY ready. Type /exit to leave.")
        while True:
            user_text = typer.prompt("You", prompt_suffix=": ")
            if user_text.strip().lower() in {"/exit", "/quit"}:
                return
            messages.append({"role": "user", "content": user_text})
            answer = chat_turn(settings, conversation, messages, True)
            messages.append({"role": "assistant", "content": answer})


@history.command("list")
def history_list() -> None:
    """List your saved conversation IDs."""
    with cli_errors():
        for identifier in Conversations(load_settings().history).list_ids():
            typer.echo(identifier)


@history.command("show")
def history_show(conversation: UUID) -> None:
    """Display one of your saved conversations."""
    with cli_errors():
        messages = Conversations(load_settings().history).read(conversation)
        if not messages:
            typer.echo("Conversation unavailable.", err=True)
            raise typer.Exit(1)
        for message in messages:
            typer.echo(f"{message['role']}: {message['content']}")


@history.command("delete")
def history_delete(conversation: UUID) -> None:
    """Delete one of your saved conversations."""
    with cli_errors():
        if not Conversations(load_settings().history).delete(conversation):
            typer.echo("Conversation unavailable.", err=True)
            raise typer.Exit(1)
        typer.echo("Conversation deleted.")


if __name__ == "__main__":
    app()
