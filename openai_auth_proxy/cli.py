from __future__ import annotations

import typer
import uvicorn

from .auth import AuthManager
from .config import Settings


app = typer.Typer(help="Local OpenAI-compatible proxy backed by ChatGPT/Codex OAuth.")


@app.command()
def login(no_browser: bool = typer.Option(False, "--no-browser", help="Print the auth URL instead of opening it.")) -> None:
    AuthManager(settings=Settings.from_env()).login(open_browser=not no_browser)
    typer.echo("Logged in.")


@app.command()
def status() -> None:
    auth_status = AuthManager(settings=Settings.from_env()).status()
    if not auth_status.logged_in:
        typer.echo("Not logged in.")
        raise typer.Exit(code=1)
    state = "expired" if auth_status.expired else "valid"
    account = f" account_id={auth_status.account_id}" if auth_status.account_id else ""
    typer.echo(f"Logged in: {state}{account}")


@app.command()
def logout() -> None:
    AuthManager(settings=Settings.from_env()).logout()
    typer.echo("Logged out.")


@app.command()
def doctor() -> None:
    info = AuthManager(settings=Settings.from_env()).doctor()
    typer.echo(f"auth_dir={info['auth_dir']}")
    typer.echo(f"server={info['server']}")
    typer.echo(f"logged_in={info['logged_in']}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(1456, "--port"),
) -> None:
    uvicorn.run("openai_auth_proxy.server:app", host=host, port=port, reload=False)
