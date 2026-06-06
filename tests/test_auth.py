import time

import pytest

from openai_auth_proxy.auth import AuthManager, doctor, login, logout, status
from openai_auth_proxy.config import Settings
from openai_auth_proxy.token_store import TokenStore
from openai_auth_proxy.types import OAuthTokens


def test_auth_manager_status_and_logout(tmp_path):
    auth_path = tmp_path / "openai_auth.json"
    settings = Settings(auth_path=auth_path)
    store = TokenStore(auth_path)
    store.save(OAuthTokens("access", "refresh", time.time() + 3600, "acc"))

    manager = AuthManager(settings=settings)
    auth_status = manager.status()

    assert auth_status.logged_in is True
    assert auth_status.expired is False
    assert auth_status.account_id == "acc"
    assert auth_status.auth_dir == tmp_path
    assert auth_status.token_path == auth_path

    manager.logout()
    assert manager.status().logged_in is False


def test_auth_convenience_functions(monkeypatch, tmp_path):
    auth_path = tmp_path / "token.json"
    monkeypatch.setenv("OPENAI_AUTH_PROXY_AUTH_PATH", str(auth_path))
    TokenStore(auth_path).save(OAuthTokens("access", "refresh", time.time() + 3600, "acc"))

    assert status().logged_in is True
    info = doctor()
    assert info["logged_in"] is True
    assert info["account_id"] == "acc"

    logout()
    assert status().logged_in is False


def test_auth_login_delegates_to_oauth(monkeypatch, tmp_path):
    settings = Settings(auth_path=tmp_path / "token.json")
    tokens = OAuthTokens("access", "refresh", time.time() + 3600, "acc")
    called = {}

    def fake_login(self, *, open_browser=True, timeout=300.0):
        called["open_browser"] = open_browser
        called["timeout"] = timeout
        return tokens

    monkeypatch.setattr("openai_auth_proxy.oauth.OpenAICodexOAuth.login_browser", fake_login)

    assert login(open_browser=False, timeout=12.0, settings=settings) == tokens
    assert called == {"open_browser": False, "timeout": 12.0}


@pytest.mark.asyncio
async def test_auth_manager_valid_tokens(tmp_path):
    auth_path = tmp_path / "openai_auth.json"
    settings = Settings(auth_path=auth_path)
    tokens = OAuthTokens("access", "refresh", time.time() + 3600, "acc")
    TokenStore(auth_path).save(tokens)

    manager = AuthManager(settings=settings)

    assert await manager.valid_tokens() == tokens
    assert await manager.refresh_if_needed() == tokens
