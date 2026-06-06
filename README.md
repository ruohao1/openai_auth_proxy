# openai-auth-proxy

Local OpenAI-compatible proxy backed by ChatGPT/Codex OAuth.

The proxy owns auth isolation, streaming conversion, OpenAI compatibility, and reasoning/event observability. Apps still own prompts, tools, MCP clients, retrieval, memory, and business logic.

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

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://127.0.0.1:1456/v1",
    api_key="unused",
    model="gpt-5.5",
    default_headers={"X-Agent-Session-Id": "my-session"},
)
```

```javascript
const es = new EventSource("http://127.0.0.1:1456/v1/agent/sessions/my-session/events")
es.addEventListener("reasoning.delta", (event) => console.log(JSON.parse(event.data).text))
```

## Commands

```bash
openai-auth-proxy login
openai-auth-proxy status
openai-auth-proxy logout
openai-auth-proxy doctor
openai-auth-proxy serve --host 127.0.0.1 --port 1456
```

## App-Facing Auth API

Apps can use the package auth API directly instead of shelling out to the `openai-auth-proxy` binary.

```python
from openai_auth_proxy.auth import login, status

auth = status()
if not auth.logged_in:
    login(open_browser=True)
```

For more control, use `AuthManager`:

```python
from openai_auth_proxy.auth import AuthManager

auth = AuthManager()
print(auth.status())
auth.login(open_browser=True)
```

The app-facing auth API is for login/status/logout orchestration. Apps should still send model traffic to the local proxy server instead of reading or using OAuth tokens directly.

## Container Usage

Use host login and container serve as the default container workflow. This keeps browser OAuth simple while still isolating app access behind the proxy.

```bash
openai-auth-proxy login
docker compose up --build
```

The compose file mounts the host auth directory into the container:

```yaml
volumes:
  - ${OPENAI_AUTH_PROXY_HOST_AUTH_DIR:-${HOME}/.local/share/openai-auth-proxy}:/auth
```

Override the host auth directory when needed:

```bash
OPENAI_AUTH_PROXY_HOST_AUTH_DIR=/path/to/auth docker compose up --build
```

The proxy is published only on localhost:

```text
127.0.0.1:1456 -> container port 1456
```

LangChain can then use the same local base URL:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://127.0.0.1:1456/v1",
    api_key="unused",
    model="gpt-5.5",
)
```

## Security

OAuth credentials are stored outside app projects. Override the auth directory with `OPENAI_AUTH_PROXY_AUTH_DIR`.

The server binds to `127.0.0.1` by default. In Docker, the service binds to `0.0.0.0` inside the container but is published to `127.0.0.1` on the host.

The proxy does not execute tools, host MCP servers, run retrieval, or access project files.
