from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str
    expires_at: float
    account_id: str | None = None

    @property
    def expired(self) -> bool:
        return self.expires_at <= time.time() + 30


@dataclass(frozen=True)
class ProviderMessage:
    role: str
    content: str


@dataclass(frozen=True)
class GenerateRequest:
    model: str
    messages: list[ProviderMessage]
    instructions: str = "You are a helpful coding assistant."
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    tool_choice: str | dict[str, Any] | None = None
    parallel_tool_calls: bool | None = None
    previous_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class GenerateResponse:
    model: str
    text: str
    raw: dict[str, Any]
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class StreamEvent:
    id: int
    type: str
    data: dict[str, Any]
