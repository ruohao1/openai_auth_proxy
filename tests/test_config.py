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
