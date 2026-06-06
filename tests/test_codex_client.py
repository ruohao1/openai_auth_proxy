import time

import httpx
import pytest

from openai_auth_proxy.codex_client import CodexClient, ProviderHTTPError
from openai_auth_proxy.config import Settings
from openai_auth_proxy.types import GenerateRequest, OAuthTokens, ProviderMessage


class FakeOAuth:
    async def valid_tokens(self):
        return OAuthTokens("access", "refresh", time.time() + 3600, "acc")


@pytest.mark.asyncio
async def test_codex_client_streams_sse_events():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            content=b'data: {"type":"response.output_text.delta","delta":"hi"}\n\ndata: [DONE]\n\n',
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CodexClient(settings=Settings(codex_api_endpoint="https://example.test/responses"), oauth=FakeOAuth(), http_client=http_client)  # type: ignore[arg-type]
    events = [event async for event in client.stream(GenerateRequest(model="gpt", messages=[ProviderMessage("user", "hi")]))]

    assert events == [{"type": "response.output_text.delta", "delta": "hi"}]
    assert requests[0].headers["authorization"] == "Bearer access"
    assert requests[0].headers["ChatGPT-Account-Id"] == "acc"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_codex_client_raises_http_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"bad")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CodexClient(settings=Settings(codex_api_endpoint="https://example.test/responses"), oauth=FakeOAuth(), http_client=http_client)  # type: ignore[arg-type]

    with pytest.raises(ProviderHTTPError):
        [event async for event in client.stream(GenerateRequest(model="gpt", messages=[]))]
    await http_client.aclose()
