import base64
import json
import time

import pytest

from openai_auth_proxy.oauth import extract_account_id, parse_jwt_claims, pkce_pair, tokens_from_response


def jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.sig"


def test_parse_jwt_claims():
    assert parse_jwt_claims(jwt({"chatgpt_account_id": "acc"}))["chatgpt_account_id"] == "acc"
    assert parse_jwt_claims("bad") == {}


def test_extract_account_id_priority():
    assert extract_account_id({"id_token": jwt({"chatgpt_account_id": "root"})}) == "root"
    assert extract_account_id({"id_token": jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "nested"}})}) == "nested"
    assert extract_account_id({"id_token": jwt({"organizations": [{"id": "org"}]})}) == "org"


def test_pkce_pair_shape():
    verifier, challenge = pkce_pair()
    assert len(verifier) == 64
    assert challenge
    assert "=" not in challenge


def test_tokens_from_response():
    tokens = tokens_from_response(
        {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "id_token": jwt({"chatgpt_account_id": "acc"}),
        }
    )
    assert tokens.access_token == "access"
    assert tokens.refresh_token == "refresh"
    assert tokens.expires_at > time.time()
    assert tokens.account_id == "acc"


def test_tokens_from_response_requires_tokens():
    with pytest.raises(Exception):
        tokens_from_response({})
