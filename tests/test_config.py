from openai_auth_proxy.config import Settings


def test_settings_uses_env_auth_path(monkeypatch, tmp_path):
    auth_path = tmp_path / "token.json"
    monkeypatch.setenv("OPENAI_AUTH_PROXY_AUTH_PATH", str(auth_path))
    settings = Settings.from_env()
    assert settings.auth_path == auth_path
    assert settings.auth_dir == tmp_path


def test_settings_supports_legacy_auth_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_AUTH_PROXY_AUTH_PATH", raising=False)
    monkeypatch.setenv("OPENAI_AUTH_PROXY_AUTH_DIR", str(tmp_path))
    settings = Settings.from_env()
    assert settings.auth_path == tmp_path / "openai_auth.json"


def test_settings_defaults_to_localhost():
    settings = Settings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 1456
    assert settings.auth_path.as_posix() == ".auth/openai_auth.json"
    assert settings.codex_api_endpoint == "https://chatgpt.com/backend-api/codex/responses"
