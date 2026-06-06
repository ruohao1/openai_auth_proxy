FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV OPENAI_AUTH_PROXY_AUTH_DIR=/auth

WORKDIR /app

COPY pyproject.toml README.md ./
COPY openai_auth_proxy ./openai_auth_proxy

RUN pip install --no-cache-dir .

EXPOSE 1456

CMD ["openai-auth-proxy", "serve", "--host", "0.0.0.0", "--port", "1456"]
