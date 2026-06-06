# OpenAI Auth Proxy Design

## Purpose

`openai-auth-proxy` is a local OpenAI-compatible gateway that lets apps use ChatGPT/Codex OAuth-backed models through standard OpenAI clients while keeping auth credentials isolated and exposing optional live reasoning, tool, and message events for observability.

## Product Boundary

The proxy owns auth isolation, streaming conversion, OpenAI compatibility, and reasoning/event observability.

Apps own prompts, agent orchestration, tool execution, MCP clients, retrieval, memory, permission flows, and business logic.

The proxy is a model access boundary, not an agent framework. It must not execute tools, host MCP servers, run retrieval, access project files, or own agent memory in the first version.

## Architecture

The package runs a local FastAPI server on `127.0.0.1` by default. Apps call OpenAI-compatible endpoints such as `/v1/chat/completions` using ordinary clients like LangChain `ChatOpenAI`. The proxy validates and refreshes OAuth credentials, converts OpenAI-shaped requests into ChatGPT Codex Responses requests, streams the upstream response back in an OpenAI-compatible shape, and publishes richer session events to separate SSE subscribers.

```text
Apps / LangChain
  |
  | POST /v1/chat/completions
  | Header: X-Agent-Session-Id
  v
openai-auth-proxy
  |
  | OAuth token refresh
  | request conversion
  v
ChatGPT Codex Responses backend
  |
  | SSE stream
  v
proxy fanout:
  |-- OpenAI-compatible response stream back to LangChain
  |-- rich SSE events to /v1/agent/sessions/{id}/events
```

## Package Shape

The Python package import name is `openai_auth_proxy`. The CLI command is `openai-auth-proxy`.

```text
openai_auth_proxy/
  __init__.py
  cli.py
  config.py
  oauth.py
  token_store.py
  codex_client.py
  compat.py
  event_bus.py
  server.py
  types.py
tests/
  test_oauth.py
  test_token_store.py
  test_compat.py
  test_event_bus.py
  test_server.py
pyproject.toml
README.md
```

## CLI

The CLI provides auth and server operations:

```bash
openai-auth-proxy login
openai-auth-proxy status
openai-auth-proxy logout
openai-auth-proxy serve --host 127.0.0.1 --port 1456
openai-auth-proxy doctor
```

`login` performs browser OAuth. `status` reports whether credentials exist and whether they are expired. `logout` clears stored credentials. `serve` starts the FastAPI server through Uvicorn. `doctor` checks local configuration and auth availability without exposing tokens.

## Auth Storage

OAuth credentials are stored outside app projects. The default directory is platform-user data under `~/.local/share/openai-auth-proxy`, with an override through `OPENAI_AUTH_PROXY_AUTH_DIR`.

The token file is `openai_auth.json`. It is written with `0600` permissions. Logs and error messages must never print access tokens, refresh tokens, or authorization headers.

The proxy automatically refreshes expired access tokens. Concurrent refresh requests are deduplicated so only one refresh call is in flight per process.

## OpenAI-Compatible Endpoints

The MVP supports:

```text
GET  /health
GET  /v1/models
POST /v1/chat/completions
POST /v1/responses
GET  /v1/agent/sessions/{session_id}/events
```

`/v1/chat/completions` is the LangChain compatibility endpoint. It supports streaming and non-streaming responses.

`/v1/responses` is the full-fidelity endpoint. It maps most directly to the upstream Codex Responses backend and should preserve richer upstream events where possible.

`/v1/models` returns known supported model IDs. It may use a static list in the MVP.

## Session Event Stream

Apps link an OpenAI-compatible request to an observability stream by setting `X-Agent-Session-Id`.

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://127.0.0.1:1456/v1",
    api_key="unused",
    model="gpt-5.5",
    default_headers={"X-Agent-Session-Id": "my-session"},
)
```

Apps listen on SSE:

```javascript
const es = new EventSource("http://127.0.0.1:1456/v1/agent/sessions/my-session/events")

es.addEventListener("reasoning.delta", (event) => {
  const data = JSON.parse(event.data)
  console.log(data.text)
})
```

Events include:

```text
request.start
request.end
reasoning.start
reasoning.delta
reasoning.end
message.delta
tool.call.start
tool.call.delta
tool.call.end
usage
error
done
```

Each event has a monotonically increasing integer ID so clients can reconnect with `?after=<event_id>`. The MVP stores recent events in memory with a configurable retention limit.

Reasoning events expose reasoning summaries or visible reasoning events only. Encrypted reasoning state is not displayed as text.

## Tools, MCP, And Retrieval

The proxy supports the OpenAI tool-calling protocol fields and observes tool-call events, but does not execute tools.

Supported request fields include:

```text
tools
tool_choice
parallel_tool_calls
```

Tool execution remains app-side. MCP clients and retrieval also remain app-side because they require project context, credentials, filesystem access, permissions, and business-specific policy.

## Streaming

The first implementation uses HTTP SSE from the upstream Codex Responses endpoint. The proxy converts upstream stream events into OpenAI-compatible chat completion chunks for `/v1/chat/completions`, while publishing richer event bus messages for subscribers.

Non-streaming requests are assembled from the same upstream stream and returned as a complete OpenAI-compatible response.

WebSocket upstream streaming is a later enhancement, not MVP scope.

## Security

The server binds to `127.0.0.1` by default. CORS is disabled by default. If browser apps need access, the user can configure allowed origins explicitly.

The proxy may support an optional local API key for app-to-proxy authentication later. It is not required for local-only MVP usage.

## MVP Scope

The MVP includes:

1. Python package scaffold.
2. CLI auth commands: `login`, `status`, `logout`, `serve`, `doctor`.
3. Secure token storage and refresh.
4. Codex Responses backend client.
5. FastAPI server with `/health`, `/v1/models`, `/v1/chat/completions`, `/v1/responses`.
6. Streaming and non-streaming chat completions.
7. Session SSE event stream with reasoning/message/tool events.
8. Tests for token storage, OAuth helpers, conversion, event bus, and server routes.

Out of scope for MVP:

1. Tool execution.
2. MCP hosting.
3. Retrieval engine.
4. Agent memory.
5. Permission approval flows.
6. Dashboard.
7. Remote multi-user deployment.
8. Upstream websocket streaming.

## Success Criteria

The package is successful when a Python project can run:

```bash
openai-auth-proxy login
openai-auth-proxy serve
```

and then use LangChain:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://127.0.0.1:1456/v1",
    api_key="unused",
    model="gpt-5.5",
)
```

without the app touching OAuth credentials. If the app provides `X-Agent-Session-Id`, it can also subscribe to live session events and display reasoning summaries separately from assistant text.
