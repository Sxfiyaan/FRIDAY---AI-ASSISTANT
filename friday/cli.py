"""Typer command line interface for FRIDAY."""

from collections.abc import Iterator
from typing import cast

import typer

from friday.config import Settings, load_settings
from friday.llm import LLMError, LLMProvider, OpenAICompatibleProvider
from friday.llm.base import Message
from friday.logging import log_event

app = typer.Typer(help="FRIDAY personal assistant")


def make_provider(settings: Settings) -> LLMProvider:
    provider = settings.selected_provider()
    if settings.provider == "groq" and not provider.api_key:
        raise LLMError(f"Missing {provider.api_key_env}; add it to your local .env file.")
    return OpenAICompatibleProvider(provider, settings.request)


def reply(provider: LLMProvider, messages: list[Message], stream: bool) -> str:
    output = provider.chat(messages, stream=stream)
    if isinstance(output, str):
        typer.echo(output)
        return output
    chunks = cast(Iterator[str], output)
    text = ""
    for chunk in chunks:
        typer.echo(chunk, nl=False)
        text += chunk
    typer.echo()
    return text


@app.command()
def chat(text: str = typer.Argument(..., help="Message to send to FRIDAY")) -> None:
    """Send a single message."""
    try:
        settings = load_settings()
        provider = make_provider(settings)
        messages: list[Message] = [{"role": "user", "content": text}]
        answer = reply(provider, messages, stream=False)
        log_event(settings.logging.path, "chat.completed", provider=settings.provider,
                  input=text, output=answer)
    except (OSError, ValueError, LLMError) as exc:
        typer.echo(f"FRIDAY: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def repl() -> None:
    """Start an interactive streaming chat session."""
    try:
        settings = load_settings()
        provider = make_provider(settings)
        messages: list[Message] = []
        typer.echo("FRIDAY ready. Type /exit to leave.")
        while True:
            user_text = typer.prompt("You", prompt_suffix=": ")
            if user_text.strip().lower() in {"/exit", "/quit"}:
                return
            messages.append({"role": "user", "content": user_text})
            answer = reply(provider, messages, stream=True)
            messages.append({"role": "assistant", "content": answer})
            log_event(settings.logging.path, "chat.turn", provider=settings.provider,
                      input=user_text, output=answer)
    except (OSError, ValueError, LLMError) as exc:
        typer.echo(f"FRIDAY: {exc}", err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
