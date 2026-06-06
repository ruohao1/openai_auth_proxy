import os
import stat
import time

from openai_auth_proxy.token_store import TokenStore
from openai_auth_proxy.types import OAuthTokens


def test_token_store_saves_loads_and_clears(tmp_path):
    store = TokenStore(tmp_path)
    tokens = OAuthTokens("access", "refresh", time.time() + 3600, "acc-123")

    store.save(tokens)
    loaded = store.load()

    assert loaded == tokens
    if os.name == "posix":
        assert stat.S_IMODE(store.path.stat().st_mode) == 0o600

    store.clear()
    assert store.load() is None
