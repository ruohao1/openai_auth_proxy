from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def default_auth_path() -> Path:
    return Path(".auth") / "openai_auth.json"


@dataclass(frozen=True)
class Settings:
    auth_path: Path = default_auth_path()
    host: str = "127.0.0.1"
    port: int = 1456
    issuer: str = "https://auth.openai.com"
    codex_api_endpoint: str = "https://chatgpt.com/backend-api/codex/responses"
    timeout: float = 120.0
    event_retention: int = 500

    @property
    def auth_dir(self) -> Path:
        return self.auth_path.parent

    @classmethod
    def from_env(cls) -> "Settings":
        auth_path = os.environ.get("OPENAI_AUTH_PROXY_AUTH_PATH")
        legacy_auth_dir = os.environ.get("OPENAI_AUTH_PROXY_AUTH_DIR")
        return cls(
            auth_path=Path(auth_path)
            if auth_path
            else Path(legacy_auth_dir) / "openai_auth.json"
            if legacy_auth_dir
            else default_auth_path(),
            host=os.environ.get("OPENAI_AUTH_PROXY_HOST", "127.0.0.1"),
            port=int(os.environ.get("OPENAI_AUTH_PROXY_PORT", "1456")),
            issuer=os.environ.get("OPENAI_AUTH_PROXY_ISSUER", "https://auth.openai.com"),
            codex_api_endpoint=os.environ.get(
                "OPENAI_AUTH_PROXY_CODEX_API_ENDPOINT",
                "https://chatgpt.com/backend-api/codex/responses",
            ),
            timeout=float(os.environ.get("OPENAI_AUTH_PROXY_TIMEOUT", "120")),
            event_retention=int(os.environ.get("OPENAI_AUTH_PROXY_EVENT_RETENTION", "500")),
        )
