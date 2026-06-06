import time

from typer.testing import CliRunner

from openai_auth_proxy.cli import app
from openai_auth_proxy.token_store import TokenStore
from openai_auth_proxy.types import OAuthTokens


def test_status_logout_and_doctor(monkeypatch, tmp_path):
    auth_path = tmp_path / "openai_auth.json"
    monkeypatch.setenv("OPENAI_AUTH_PROXY_AUTH_PATH", str(auth_path))
    runner = CliRunner()
    store = TokenStore(auth_path)
    store.save(OAuthTokens("access", "refresh", time.time() + 3600, "acc"))

    status = runner.invoke(app, ["status"])
    assert status.exit_code == 0
    assert "Logged in: valid" in status.output

    doctor = runner.invoke(app, ["doctor"])
    assert doctor.exit_code == 0
    assert f"auth_path={auth_path}" in doctor.output
    assert "logged_in=True" in doctor.output

    logout = runner.invoke(app, ["logout"])
    assert logout.exit_code == 0
    assert store.load() is None
