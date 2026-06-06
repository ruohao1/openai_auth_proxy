from __future__ import annotations

import json
import time
import uuid
from typing import Any

from .types import GenerateRequest, ProviderMessage


def chat_messages_to_provider(messages: list[dict[str, Any]]) -> list[ProviderMessage]:
    result: list[ProviderMessage] = []
    for message in messages:
        role = str(message.get("role", "user"))
        content = message.get("content", "")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(_content_part_text(part) for part in content)
        else:
            text = str(content)
        result.append(ProviderMessage(role=role, content=text))
    return result


def chat_request_to_generate(body: dict[str, Any]) -> GenerateRequest:
    return GenerateRequest(
        model=str(body.get("model", "gpt-5.5")),
        messages=chat_messages_to_provider(list(body.get("messages") or [])),
        temperature=_optional_float(body.get("temperature")),
        max_tokens=_optional_int(body.get("max_tokens") or body.get("max_completion_tokens")),
        tools=list(body.get("tools") or []),
        tool_choice=body.get("tool_choice"),
        parallel_tool_calls=body.get("parallel_tool_calls"),
    )


def generate_to_codex_payload(request: GenerateRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": request.model,
        "instructions": request.instructions,
        "store": False,
        "stream": True,
        "input": messages_to_input(request.messages)
        + request.previous_tool_calls
        + request.tool_results,
    }
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.max_tokens is not None:
        payload["max_output_tokens"] = request.max_tokens
    if request.tools:
        payload["tools"] = request.tools
    if request.tool_choice is not None:
        payload["tool_choice"] = request.tool_choice
    if request.parallel_tool_calls is not None:
        payload["parallel_tool_calls"] = request.parallel_tool_calls
    return payload


def messages_to_input(messages: list[ProviderMessage]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for message in messages:
        role = _response_role(message.role)
        content_type = "output_text" if role == "assistant" else "input_text"
        items.append(
            {
                "type": "message",
                "role": role,
                "content": [{"type": content_type, "text": message.content}],
            }
        )
    return items


def extract_text(raw: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in raw.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "".join(parts)


def extract_tool_calls(raw: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for item in raw.get("output", []):
        if isinstance(item, dict) and item.get("type") in {"function_call", "tool_call"}:
            calls.append(item)
    return calls


def extract_stream_text_delta(event: dict[str, Any]) -> str:
    if isinstance(event.get("delta"), str) and "output_text" in str(event.get("type", "")):
        return event["delta"]
    item = event.get("item")
    if isinstance(item, dict):
        return extract_text({"output": [item]})
    response = event.get("response")
    if isinstance(response, dict):
        return extract_text(response)
    return ""


def extract_stream_reasoning_delta(event: dict[str, Any]) -> str:
    event_type = str(event.get("type", ""))
    if "reasoning" not in event_type:
        return ""
    delta = event.get("delta") or event.get("text")
    return delta if isinstance(delta, str) else ""


def chat_completion_response(model: str, raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(raw.get("id") or f"chatcmpl-{uuid.uuid4().hex}"),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": extract_text(raw)},
                "finish_reason": _finish_reason(raw),
            }
        ],
        "usage": raw.get("usage"),
    }


def chat_completion_chunk(model: str, content: str, *, finish_reason: str | None = None) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    if content:
        delta["content"] = content
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


def sse_data(payload: dict[str, Any] | str) -> bytes:
    if isinstance(payload, str):
        body = payload
    else:
        body = json.dumps(payload, separators=(",", ":"))
    return f"data: {body}\n\n".encode()


def event_sse(event_id: int, event_type: str, data: dict[str, Any]) -> str:
    return f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def _content_part_text(part: object) -> str:
    if isinstance(part, dict):
        text = part.get("text")
        return text if isinstance(text, str) else str(part)
    return str(part)


def _response_role(role: str) -> str:
    if role in {"human", "user"}:
        return "user"
    if role in {"ai", "assistant"}:
        return "assistant"
    if role in {"system", "developer"}:
        return role
    return "user"


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _finish_reason(raw: dict[str, Any]) -> str:
    status = raw.get("status")
    if status in {"completed", "complete"}:
        return "stop"
    return "stop"
