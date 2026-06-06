import json

import pytest
from fastapi.testclient import TestClient

from openai_auth_proxy.event_bus import EventBus
from openai_auth_proxy.server import create_app
from openai_auth_proxy.types import GenerateResponse


class FakeCodexClient:
    async def generate(self, request):
        raw = {"id": "resp", "status": "completed", "output": [{"content": [{"text": "hello"}]}]}
        return GenerateResponse(model=getattr(request, "model", "gpt-5.5"), text="hello", raw=raw)

    async def stream(self, request):
        yield {"type": "response.output_text.delta", "delta": "hello"}
        yield {"type": "response.completed", "response": {"usage": {"output_tokens": 1}}}


def test_health_and_models():
    client = TestClient(create_app(codex_client=FakeCodexClient()))  # type: ignore[arg-type]
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/v1/models").json()["data"]


def test_chat_completions_non_streaming():
    client = TestClient(create_app(codex_client=FakeCodexClient()))  # type: ignore[arg-type]
    response = client.post("/v1/chat/completions", json={"model": "gpt-5.5", "messages": []})
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "hello"


def test_chat_completions_streaming():
    client = TestClient(create_app(codex_client=FakeCodexClient()))  # type: ignore[arg-type]
    response = client.post("/v1/chat/completions", json={"model": "gpt-5.5", "messages": [], "stream": True})
    assert response.status_code == 200
    assert "data: [DONE]" in response.text


@pytest.mark.asyncio
async def test_non_streaming_request_publishes_events():
    bus = EventBus()
    client = TestClient(create_app(codex_client=FakeCodexClient(), event_bus=bus))  # type: ignore[arg-type]
    response = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-5.5", "messages": []},
        headers={"X-Agent-Session-Id": "s"},
    )
    assert response.status_code == 200
    assert [event.type for event in bus.history("s")] == ["request.start", "message.delta", "request.end", "done"]


def test_responses_stream_passthrough():
    client = TestClient(create_app(codex_client=FakeCodexClient()))  # type: ignore[arg-type]
    response = client.post("/v1/responses", json={"model": "gpt-5.5", "input": [], "stream": True})
    assert response.status_code == 200
    assert json.loads(response.text.split("data: ")[1].split("\n", 1)[0])["delta"] == "hello"
