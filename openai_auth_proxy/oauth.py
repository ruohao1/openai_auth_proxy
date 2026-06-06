from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from .config import Settings
from .token_store import TokenStore
from .types import OAuthTokens


CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CALLBACK_PATH = "/auth/callback"
OAUTH_PORT = 1455


class OAuthError(RuntimeError):
    pass


class OpenAICodexOAuth:
    def __init__(self, *, settings: Settings | None = None, token_store: TokenStore | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.token_store = token_store or TokenStore(self.settings.auth_dir)
        self._refresh_lock = asyncio.Lock()

    @property
    def redirect_uri(self) -> str:
        return f"http://localhost:{OAUTH_PORT}{CALLBACK_PATH}"

    def authorization_url(self, *, code_challenge: str, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": self.redirect_uri,
            "scope": "openid profile email offline_access",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "state": state,
            "originator": "openai-auth-proxy",
        }
        return f"{self.settings.issuer.rstrip('/')}/oauth/authorize?{urlencode(params)}"

    def login_browser(self, *, open_browser: bool = True, timeout: float = 300.0) -> OAuthTokens:
        verifier, challenge = pkce_pair()
        state = random_urlsafe(32)
        code_result: dict[str, str] = {}
        error_result: dict[str, str] = {}
        server = self._callback_server(state, code_result, error_result)
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        auth_url = self.authorization_url(code_challenge=challenge, state=state)
        if open_browser:
            webbrowser.open(auth_url)
        else:
            print(auth_url)
        thread.join(timeout)
        server.server_close()
        if thread.is_alive():
            raise OAuthError("OAuth callback timed out")
        if error_result:
            raise OAuthError(error_result.get("message", "OAuth authorization failed"))
        code = code_result.get("code")
        if not code:
            raise OAuthError("OAuth callback did not include an authorization code")
        tokens = asyncio.run(self.exchange_code(code=code, code_verifier=verifier, redirect_uri=self.redirect_uri))
        self.token_store.save(tokens)
        return tokens

    async def valid_tokens(self) -> OAuthTokens:
        tokens = self.token_store.load()
        if not tokens:
            raise OAuthError("Run openai-auth-proxy login before using the proxy")
        if not tokens.expired:
            return tokens
        async with self._refresh_lock:
            current = self.token_store.load()
            if current and not current.expired:
                return current
            if not current:
                raise OAuthError("Run openai-auth-proxy login before using the proxy")
            refreshed = await self.refresh(current.refresh_token, account_id=current.account_id)
            self.token_store.save(refreshed)
            return refreshed

    async def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> OAuthTokens:
        data = await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": CLIENT_ID,
                "code_verifier": code_verifier,
            }
        )
        return tokens_from_response(data)

    async def refresh(self, refresh_token: str, *, account_id: str | None = None) -> OAuthTokens:
        data = await self._token_request(
            {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": CLIENT_ID}
        )
        tokens = tokens_from_response(data)
        if tokens.account_id is None:
            tokens.account_id = account_id
        return tokens

    async def _token_request(self, form: dict[str, str]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.settings.issuer.rstrip('/')}/oauth/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=form,
            )
        if not response.is_success:
            raise OAuthError(f"OAuth token request failed with HTTP {response.status_code}: {response.text}")
        data = response.json()
        if not isinstance(data, dict):
            raise OAuthError("OAuth token response was not a JSON object")
        return data

    def _callback_server(
        self,
        expected_state: str,
        code_result: dict[str, str],
        error_result: dict[str, str],
    ) -> HTTPServer:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler_self) -> None:  # noqa: N802
                parsed = urlparse(handler_self.path)
                if parsed.path != CALLBACK_PATH:
                    handler_self.send_response(404)
                    handler_self.end_headers()
                    return
                params = parse_qs(parsed.query)
                state = params.get("state", [None])[0]
                if state != expected_state:
                    error_result["message"] = "Invalid OAuth state"
                    handler_self._html(400, "Authorization failed. You can close this window.")
                    return
                error = params.get("error_description", params.get("error", [None]))[0]
                if error:
                    error_result["message"] = error
                    handler_self._html(400, "Authorization failed. You can close this window.")
                    return
                code = params.get("code", [None])[0]
                if not code:
                    error_result["message"] = "Missing authorization code"
                    handler_self._html(400, "Authorization failed. You can close this window.")
                    return
                code_result["code"] = code
                handler_self._html(200, "Authorization successful. You can close this window.")

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _html(self, status: int, message: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"<html><body><p>{message}</p></body></html>".encode())

        return HTTPServer(("localhost", OAUTH_PORT), Handler)


def pkce_pair() -> tuple[str, str]:
    verifier = random_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def random_urlsafe(length: int) -> str:
    return secrets.token_urlsafe(length)[:length]


def parse_jwt_claims(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def extract_account_id(data: dict[str, Any]) -> str | None:
    for token_name in ("id_token", "access_token"):
        token = data.get(token_name)
        if not isinstance(token, str):
            continue
        claims = parse_jwt_claims(token)
        auth_claim = claims.get("https://api.openai.com/auth")
        nested = auth_claim.get("chatgpt_account_id") if isinstance(auth_claim, dict) else None
        account_id = claims.get("chatgpt_account_id") or nested
        if isinstance(account_id, str):
            return account_id
        organizations = claims.get("organizations")
        if isinstance(organizations, list) and organizations and isinstance(organizations[0], dict):
            org_id = organizations[0].get("id")
            if isinstance(org_id, str):
                return org_id
    return None


def tokens_from_response(data: dict[str, Any]) -> OAuthTokens:
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    if not isinstance(access, str) or not isinstance(refresh, str):
        raise OAuthError("OAuth token response did not include access_token and refresh_token")
    return OAuthTokens(
        access_token=access,
        refresh_token=refresh,
        expires_at=time.time() + float(data.get("expires_in") or 3600),
        account_id=extract_account_id(data),
    )
