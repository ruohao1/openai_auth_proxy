from __future__ import annotations

import typer
import uvicorn

from .config import Settings
from .oauth import OAuthError, OpenAICodexOAuth
from .token_store import TokenStore


app = typer.Typer(help="Local OpenAI-compatible proxy backed by ChatGPT/Codex OAuth.")


@app.command()
def login(no_browser: bool = typer.Option(False, "--no-browser", help="Print the auth URL instead of opening it.")) -> None:
    oauth = OpenAICodexOAuth(settings=Settings.from_env())
    oauth.login_browser(open_browser=not no_browser)
    typer.echo("Logged in.")


@app.command()
def status() -> None:
    tokens = TokenStore(Settings.from_env().auth_dir).load()
    if not tokens:
        typer.echo("Not logged in.")
        raise typer.Exit(code=1)
    state = "expired" if tokens.expired else "valid"
    account = f" account_id={tokens.account_id}" if tokens.account_id else ""
    typer.echo(f"Logged in: {state}{account}")


@app.command()
def logout() -> None:
    TokenStore(Settings.from_env().auth_dir).clear()
    typer.echo("Logged out.")


@app.command()
def doctor() -> None:
    settings = Settings.from_env()
    tokens = TokenStore(settings.auth_dir).load()
    typer.echo(f"auth_dir={settings.auth_dir}")
    typer.echo(f"server=http://{settings.host}:{settings.port}")
    typer.echo(f"logged_in={tokens is not None}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(1456, "--port"),
) -> None:
    uvicorn.run("openai_auth_proxy.server:app", host=host, port=port, reload=False)
