from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def default_auth_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "openai-auth-proxy"


@dataclass(frozen=True)
class Settings:
    auth_dir: Path = default_auth_dir()
    host: str = "127.0.0.1"
    port: int = 1456
    issuer: str = "https://auth.openai.com"
    codex_api_endpoint: str = "https://chatgpt.com/backend-api/codex/responses"
    timeout: float = 120.0
    event_retention: int = 500

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            auth_dir=Path(os.environ.get("OPENAI_AUTH_PROXY_AUTH_DIR", default_auth_dir())),
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
