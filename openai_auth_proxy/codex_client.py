from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .compat import extract_text, extract_tool_calls, generate_to_codex_payload
from .config import Settings
from .oauth import OpenAICodexOAuth
from .types import GenerateRequest, GenerateResponse


class ProviderHTTPError(RuntimeError):
    def __init__(self, message: str, *, status_code: int, body: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class CodexClient:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        oauth: OpenAICodexOAuth | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.oauth = oauth or OpenAICodexOAuth(settings=self.settings)
        self.http_client = http_client

    async def stream(self, request: GenerateRequest | dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        payload = generate_to_codex_payload(request) if isinstance(request, GenerateRequest) else request
        tokens = await self.oauth.valid_tokens()
        headers = {
            "Authorization": f"Bearer {tokens.access_token}",
            "Content-Type": "application/json",
            "originator": "openai-auth-proxy",
        }
        if tokens.account_id:
            headers["ChatGPT-Account-Id"] = tokens.account_id

        if self.http_client is not None:
            async with self.http_client.stream(
                "POST",
                self.settings.codex_api_endpoint,
                headers=headers,
                json=payload,
                timeout=self.settings.timeout,
            ) as response:
                async for event in _iter_sse(response):
                    yield event
            return

        async with httpx.AsyncClient(timeout=self.settings.timeout) as client:
            async with client.stream(
                "POST",
                self.settings.codex_api_endpoint,
                headers=headers,
                json=payload,
            ) as response:
                async for event in _iter_sse(response):
                    yield event

    async def generate(self, request: GenerateRequest | dict[str, Any]) -> GenerateResponse:
        output: list[dict[str, Any]] = []
        final_response: dict[str, Any] | None = None
        model = request.model if isinstance(request, GenerateRequest) else str(request.get("model", ""))
        async for event in self.stream(request):
            if event.get("type") == "response.output_item.done" and isinstance(event.get("item"), dict):
                output.append(event["item"])
            if event.get("type") == "response.completed" and isinstance(event.get("response"), dict):
                final_response = event["response"]
        raw = final_response or {"output": output}
        if output and not raw.get("output"):
            raw["output"] = output
        return GenerateResponse(model=model, text=extract_text(raw), raw=raw, tool_calls=extract_tool_calls(raw))


async def _iter_sse(response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
    if not response.is_success:
        body = await response.aread()
        raise ProviderHTTPError(
            f"Request failed with HTTP {response.status_code}",
            status_code=response.status_code,
            body=body.decode("utf-8", errors="replace"),
        )
    async for line in response.aiter_lines():
        if not line or not line.startswith("data: "):
            continue
        payload = line.removeprefix("data: ")
        if payload == "[DONE]":
            break
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            yield event
