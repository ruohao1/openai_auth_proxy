import json

from openai_auth_proxy.compat import (
    chat_completion_response,
    chat_messages_to_provider,
    chat_request_to_generate,
    extract_stream_reasoning_delta,
    extract_stream_text_delta,
    extract_text,
    generate_to_codex_payload,
    sse_data,
)


def test_chat_request_to_codex_payload_forwards_tools():
    request = chat_request_to_generate(
        {
            "model": "gpt-5.5",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [{"type": "function", "function": {"name": "lookup"}}],
            "tool_choice": "auto",
        }
    )
    payload = generate_to_codex_payload(request)
    assert payload["model"] == "gpt-5.5"
    assert payload["tools"][0]["function"]["name"] == "lookup"
    assert payload["tool_choice"] == "auto"
    assert payload["input"][0]["role"] == "user"


def test_chat_messages_to_provider_handles_parts():
    messages = chat_messages_to_provider([{"role": "user", "content": [{"type": "text", "text": "hi"}]}])
    assert messages[0].content == "hi"


def test_extract_text_and_response():
    raw = {"output": [{"content": [{"text": "hello"}, {"text": " world"}]}]}
    assert extract_text(raw) == "hello world"
    response = chat_completion_response("gpt-5.5", raw)
    assert response["choices"][0]["message"]["content"] == "hello world"


def test_stream_delta_extractors():
    assert extract_stream_text_delta({"type": "response.output_text.delta", "delta": "x"}) == "x"
    assert extract_stream_reasoning_delta({"type": "response.reasoning.delta", "delta": "thinking"}) == "thinking"


def test_sse_data_formats_json():
    payload = sse_data({"a": 1}).decode()
    assert payload.startswith("data: ")
    assert json.loads(payload.removeprefix("data: ").strip()) == {"a": 1}
