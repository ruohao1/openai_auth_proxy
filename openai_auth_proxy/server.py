from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .codex_client import CodexClient, ProviderHTTPError
from .compat import (
    chat_completion_chunk,
    chat_completion_response,
    chat_request_to_generate,
    event_sse,
    extract_stream_reasoning_delta,
    extract_stream_text_delta,
    generate_to_codex_payload,
    sse_data,
)
from .config import Settings
from .event_bus import EventBus
from .oauth import OAuthError, OpenAICodexOAuth


KNOWN_MODELS = ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex-spark"]


def create_app(
    *,
    settings: Settings | None = None,
    oauth: OpenAICodexOAuth | None = None,
    codex_client: CodexClient | None = None,
    event_bus: EventBus | None = None,
) -> FastAPI:
    app_settings = settings or Settings.from_env()
    bus = event_bus or EventBus(retention=app_settings.event_retention)
    client = codex_client or CodexClient(settings=app_settings, oauth=oauth)
    app = FastAPI(title="openai-auth-proxy")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models")
    async def models() -> dict[str, Any]:
        return {"object": "list", "data": [{"id": model, "object": "model"} for model in KNOWN_MODELS]}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request, x_agent_session_id: str | None = Header(default=None)):
        body = await request.json()
        generate_request = chat_request_to_generate(body)
        session_id = x_agent_session_id
        if session_id:
            await bus.publish(session_id, "request.start", {"model": generate_request.model})
        try:
            if body.get("stream"):
                return StreamingResponse(
                    _stream_chat(client, bus, session_id, generate_request),
                    media_type="text/event-stream",
                )
            response = await client.generate(generate_request)
            if session_id:
                if response.text:
                    await bus.publish(session_id, "message.delta", {"text": response.text})
                await bus.publish(session_id, "request.end", {"model": generate_request.model})
                await bus.publish(session_id, "done", {})
            return chat_completion_response(generate_request.model, response.raw)
        except (OAuthError, ProviderHTTPError) as error:
            if session_id:
                await bus.publish(session_id, "error", {"message": str(error)})
            raise _http_error(error) from error

    @app.post("/v1/responses")
    async def responses(request: Request, x_agent_session_id: str | None = Header(default=None)):
        body = await request.json()
        if x_agent_session_id:
            await bus.publish(x_agent_session_id, "request.start", {"model": body.get("model")})
        try:
            if body.get("stream"):
                return StreamingResponse(
                    _stream_responses(client, bus, x_agent_session_id, body),
                    media_type="text/event-stream",
                )
            response = await client.generate(body)
            if x_agent_session_id:
                await bus.publish(x_agent_session_id, "request.end", {"model": body.get("model")})
                await bus.publish(x_agent_session_id, "done", {})
            return JSONResponse(response.raw)
        except (OAuthError, ProviderHTTPError) as error:
            if x_agent_session_id:
                await bus.publish(x_agent_session_id, "error", {"message": str(error)})
            raise _http_error(error) from error

    @app.get("/v1/agent/sessions/{session_id}/events")
    async def session_events(session_id: str, after: int = 0):
        async def stream() -> AsyncIterator[str]:
            async for event in bus.subscribe(session_id, after=after):
                yield event_sse(event.id, event.type, event.data)

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app


async def _stream_chat(
    client: CodexClient,
    bus: EventBus,
    session_id: str | None,
    generate_request,
) -> AsyncIterator[bytes]:
    try:
        async for event in client.stream(generate_request):
            await _publish_observed_event(bus, session_id, event)
            text = extract_stream_text_delta(event)
            if text:
                yield sse_data(chat_completion_chunk(generate_request.model, text))
        if session_id:
            await bus.publish(session_id, "request.end", {"model": generate_request.model})
            await bus.publish(session_id, "done", {})
        yield sse_data(chat_completion_chunk(generate_request.model, "", finish_reason="stop"))
        yield sse_data("[DONE]")
    except Exception as error:
        if session_id:
            await bus.publish(session_id, "error", {"message": str(error)})
        raise


async def _stream_responses(
    client: CodexClient,
    bus: EventBus,
    session_id: str | None,
    body: dict[str, Any],
) -> AsyncIterator[bytes]:
    try:
        async for event in client.stream(body):
            await _publish_observed_event(bus, session_id, event)
            yield sse_data(event)
        if session_id:
            await bus.publish(session_id, "request.end", {"model": body.get("model")})
            await bus.publish(session_id, "done", {})
        yield sse_data("[DONE]")
    except Exception as error:
        if session_id:
            await bus.publish(session_id, "error", {"message": str(error)})
        raise


async def _publish_observed_event(bus: EventBus, session_id: str | None, event: dict[str, Any]) -> None:
    if not session_id:
        return
    reasoning = extract_stream_reasoning_delta(event)
    if reasoning:
        await bus.publish(session_id, "reasoning.delta", {"text": reasoning})
    text = extract_stream_text_delta(event)
    if text:
        await bus.publish(session_id, "message.delta", {"text": text})
    if event.get("type") in {"response.output_item.done", "response.function_call_arguments.done"}:
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") in {"function_call", "tool_call"}:
            await bus.publish(session_id, "tool.call.end", item)
    if event.get("type") == "response.completed" and isinstance(event.get("response"), dict):
        usage = event["response"].get("usage")
        if isinstance(usage, dict):
            await bus.publish(session_id, "usage", usage)


def _http_error(error: Exception) -> HTTPException:
    status = 401 if isinstance(error, OAuthError) else getattr(error, "status_code", 500)
    return HTTPException(status_code=status, detail={"error": {"message": str(error), "type": type(error).__name__}})


app = create_app()
