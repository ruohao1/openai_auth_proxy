from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .oauth import OpenAICodexOAuth
from .token_store import TokenStore
from .types import OAuthTokens


@dataclass(frozen=True)
class AuthStatus:
    logged_in: bool
    expired: bool | None
    account_id: str | None
    auth_dir: Path
    token_path: Path


class AuthManager:
    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.token_store = TokenStore(self.settings.auth_path)
        self.oauth = OpenAICodexOAuth(settings=self.settings, token_store=self.token_store)

    def login(self, *, open_browser: bool = True, timeout: float = 300.0) -> OAuthTokens:
        return self.oauth.login_browser(open_browser=open_browser, timeout=timeout)

    def status(self) -> AuthStatus:
        tokens = self.token_store.load()
        return AuthStatus(
            logged_in=tokens is not None,
            expired=tokens.expired if tokens else None,
            account_id=tokens.account_id if tokens else None,
            auth_dir=self.token_store.auth_dir,
            token_path=self.token_store.path,
        )

    def logout(self) -> None:
        self.token_store.clear()

    async def valid_tokens(self) -> OAuthTokens:
        return await self.oauth.valid_tokens()

    async def refresh_if_needed(self) -> OAuthTokens:
        return await self.oauth.valid_tokens()

    def doctor(self) -> dict[str, Any]:
        status = self.status()
        return {
            "auth_dir": status.auth_dir,
            "token_path": status.token_path,
            "server": f"http://{self.settings.host}:{self.settings.port}",
            "logged_in": status.logged_in,
            "expired": status.expired,
            "account_id": status.account_id,
        }


def login(*, open_browser: bool = True, timeout: float = 300.0, settings: Settings | None = None) -> OAuthTokens:
    return AuthManager(settings=settings).login(open_browser=open_browser, timeout=timeout)


def status(*, settings: Settings | None = None) -> AuthStatus:
    return AuthManager(settings=settings).status()


def logout(*, settings: Settings | None = None) -> None:
    AuthManager(settings=settings).logout()


def doctor(*, settings: Settings | None = None) -> dict[str, Any]:
    return AuthManager(settings=settings).doctor()
