# OpenAI Auth Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python `openai-auth-proxy` package that exposes a local OpenAI-compatible API backed by ChatGPT/Codex OAuth and emits optional live session events.

**Architecture:** The package is a FastAPI server plus Typer CLI. OAuth/token storage and Codex request logic live in focused modules, while OpenAI compatibility conversion and event fanout are separate units. Apps interact only through local HTTP endpoints and never read OAuth credentials.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Typer, httpx, Pydantic, pytest, pytest-asyncio.

---

## File Structure

- Create `pyproject.toml`: package metadata, dependencies, CLI entry point, pytest config.
- Create `README.md`: installation, login, serve, LangChain, and event stream examples.
- Create `openai_auth_proxy/__init__.py`: package exports and version.
- Create `openai_auth_proxy/types.py`: shared dataclasses and Pydantic models.
- Create `openai_auth_proxy/config.py`: environment-driven settings.
- Create `openai_auth_proxy/token_store.py`: secure token load/save/clear.
- Create `openai_auth_proxy/oauth.py`: PKCE browser login, token exchange, refresh, account ID extraction, refresh deduplication.
- Create `openai_auth_proxy/codex_client.py`: upstream Codex Responses client and SSE parser.
- Create `openai_auth_proxy/compat.py`: OpenAI Chat/Responses request and response conversion.
- Create `openai_auth_proxy/event_bus.py`: in-memory per-session event history and SSE subscription.
- Create `openai_auth_proxy/server.py`: FastAPI app and routes.
- Create `openai_auth_proxy/cli.py`: Typer CLI commands.
- Create tests under `tests/` for each module.

## Task 1: Package Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `openai_auth_proxy/__init__.py`
- Test: none

- [ ] **Step 1: Create package metadata**

Create `pyproject.toml` with:

```toml
[project]
name = "openai-auth-proxy"
version = "0.1.0"
description = "Local OpenAI-compatible proxy backed by ChatGPT/Codex OAuth"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "httpx>=0.27.0",
    "pydantic>=2.8.0",
    "typer>=0.12.0",
    "uvicorn>=0.30.0",
]

[project.optional-dependencies]
test = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[project.scripts]
openai-auth-proxy = "openai_auth_proxy.cli:app"

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["openai_auth_proxy*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create package init**

Create `openai_auth_proxy/__init__.py` with:

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Create README**

Create `README.md` with:

```markdown
# openai-auth-proxy

Local OpenAI-compatible proxy backed by ChatGPT/Codex OAuth.

## Quick Start

```bash
openai-auth-proxy login
openai-auth-proxy serve
```

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://127.0.0.1:1456/v1",
    api_key="unused",
    model="gpt-5.5",
)
```

## Session Events

Pass `X-Agent-Session-Id` to link a model request with the event stream.

```javascript
const es = new EventSource("http://127.0.0.1:1456/v1/agent/sessions/my-session/events")
es.addEventListener("reasoning.delta", (event) => console.log(JSON.parse(event.data).text))
```
```

- [ ] **Step 4: Verify metadata parses**

Run: `python -m pip install -e .[test]`

Expected: package installs successfully.

## Task 2: Types And Config

**Files:**
- Create: `openai_auth_proxy/types.py`
- Create: `openai_auth_proxy/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write config tests**

Create `tests/test_config.py` with:

```python
from pathlib import Path

from openai_auth_proxy.config import Settings


def test_settings_uses_env_auth_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_AUTH_PROXY_AUTH_DIR", str(tmp_path))
    settings = Settings.from_env()
    assert settings.auth_dir == tmp_path


def test_settings_defaults_to_localhost():
    settings = Settings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 1456
    assert settings.codex_api_endpoint == "https://chatgpt.com/backend-api/codex/responses"
```

- [ ] **Step 2: Implement types**

Create `openai_auth_proxy/types.py` with dataclasses for `OAuthTokens`, `ProviderMessage`, `GenerateRequest`, `GenerateResponse`, and `StreamEvent`.

- [ ] **Step 3: Implement config**

Create `openai_auth_proxy/config.py` with a `Settings` dataclass, `from_env()`, default auth directory, host, port, issuer, endpoint, timeout, and event retention.

- [ ] **Step 4: Run config tests**

Run: `pytest tests/test_config.py -v`

Expected: all tests pass.

## Task 3: Secure Token Store

**Files:**
- Create: `openai_auth_proxy/token_store.py`
- Test: `tests/test_token_store.py`

- [ ] **Step 1: Write token store tests**

Create tests that save tokens, verify reload, verify file mode is `0600` on POSIX, and verify `clear()` removes the file.

- [ ] **Step 2: Implement token store**

Implement `TokenStore.load()`, `save()`, and `clear()` using JSON and `Path.chmod(0o600)`.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_token_store.py -v`

Expected: all tests pass.

## Task 4: OAuth Helpers

**Files:**
- Create: `openai_auth_proxy/oauth.py`
- Test: `tests/test_oauth.py`

- [ ] **Step 1: Write OAuth helper tests**

Test JWT claim parsing, account ID extraction priority, PKCE challenge shape, and refresh deduplication with a fake async refresh function.

- [ ] **Step 2: Implement OAuth helpers**

Implement browser PKCE login, authorization URL building, token exchange, refresh, valid token loading, account extraction, and a process-local lock for refresh deduplication.

- [ ] **Step 3: Run OAuth tests**

Run: `pytest tests/test_oauth.py -v`

Expected: all tests pass.

## Task 5: Event Bus

**Files:**
- Create: `openai_auth_proxy/event_bus.py`
- Test: `tests/test_event_bus.py`

- [ ] **Step 1: Write event bus tests**

Test publishing events, retaining event IDs, replaying `after`, retention trimming, and subscriber delivery.

- [ ] **Step 2: Implement event bus**

Implement `EventBus.publish()`, `history()`, and async `subscribe()` with per-session queues and in-memory retention.

- [ ] **Step 3: Run event bus tests**

Run: `pytest tests/test_event_bus.py -v`

Expected: all tests pass.

## Task 6: OpenAI Compatibility Conversion

**Files:**
- Create: `openai_auth_proxy/compat.py`
- Test: `tests/test_compat.py`

- [ ] **Step 1: Write conversion tests**

Test chat messages to Codex input, tool forwarding, text extraction, tool call extraction, non-streaming chat completion assembly, and SSE chat chunk formatting.

- [ ] **Step 2: Implement conversion**

Implement request conversion for chat completions and responses, extraction helpers, and response chunk builders.

- [ ] **Step 3: Run conversion tests**

Run: `pytest tests/test_compat.py -v`

Expected: all tests pass.

## Task 7: Codex Client

**Files:**
- Create: `openai_auth_proxy/codex_client.py`
- Test: `tests/test_codex_client.py`

- [ ] **Step 1: Write client tests**

Use an injected fake `httpx.AsyncClient` transport to test headers, account ID header, HTTP error handling, SSE event parsing, and final output assembly.

- [ ] **Step 2: Implement client**

Implement `CodexClient.stream()` and `CodexClient.generate()` using `httpx.AsyncClient.stream()` and an SSE parser for `data: ...` lines.

- [ ] **Step 3: Run client tests**

Run: `pytest tests/test_codex_client.py -v`

Expected: all tests pass.

## Task 8: FastAPI Server

**Files:**
- Create: `openai_auth_proxy/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write route tests**

Test `/health`, `/v1/models`, non-streaming `/v1/chat/completions`, streaming `/v1/chat/completions`, `/v1/responses`, and `/v1/agent/sessions/{session_id}/events` using dependency overrides or injected fake client objects.

- [ ] **Step 2: Implement server factory**

Implement `create_app(settings=None, oauth=None, codex_client=None, event_bus=None)`.

- [ ] **Step 3: Implement routes**

Implement health, models, chat completions, responses passthrough, and session SSE routes. Publish request, message, reasoning, tool, usage, error, and done events where available.

- [ ] **Step 4: Run server tests**

Run: `pytest tests/test_server.py -v`

Expected: all tests pass.

## Task 9: CLI

**Files:**
- Create: `openai_auth_proxy/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write CLI tests**

Test `status`, `logout`, and `doctor` with temporary auth directories and mocked OAuth. Do not test real browser login.

- [ ] **Step 2: Implement CLI**

Implement Typer commands `login`, `status`, `logout`, `serve`, and `doctor`.

- [ ] **Step 3: Run CLI tests**

Run: `pytest tests/test_cli.py -v`

Expected: all tests pass.

## Task 10: End-To-End Verification

**Files:**
- Modify: `README.md`
- Test: all tests

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`

Expected: all tests pass.

- [ ] **Step 2: Run import smoke test**

Run: `python -c "import openai_auth_proxy; print(openai_auth_proxy.__version__)"`

Expected: prints `0.1.0`.

- [ ] **Step 3: Run CLI help smoke test**

Run: `openai-auth-proxy --help`

Expected: command lists `login`, `status`, `logout`, `serve`, and `doctor`.

- [ ] **Step 4: Final README update**

Ensure README contains CLI examples, LangChain examples, event stream examples, security boundary, and MVP limitations.

## Self-Review

Spec coverage: the plan covers package scaffold, auth storage, OAuth, refresh, Codex client, OpenAI compatibility, streaming, session events, server routes, CLI, and tests. It explicitly excludes tool execution, MCP hosting, retrieval, dashboard, remote deployment, and upstream websocket streaming.

Placeholder scan: no task relies on an undefined future feature. Each task names files, tests, commands, and expected results.

Type consistency: package name is consistently `openai_auth_proxy`; CLI command is consistently `openai-auth-proxy`; event stream uses `X-Agent-Session-Id` and `/v1/agent/sessions/{session_id}/events` throughout.
