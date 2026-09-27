from __future__ import annotations

import pytest

from seventhings import APIError
from seventhings.models import SSOAppTarget, SSOProviderName

from .conftest import Harness

TOKEN_BODY = {
    "access_token": "new-access",
    "expires_in": 3600,
    "token_type": "Bearer",
    "scope": None,
    "refresh_token": "refresh-1",
    "user_id": 1,
}


def test_ping_is_unauthenticated(h: Harness) -> None:
    h.respond(json_body={"status": "OK", "description": "Customer API"})
    ping = h.call(lambda c: c.ping())
    assert ping.status == "OK"
    assert h.path() == ""
    assert h.last.url.raw_path == b"/customer-api/v1"
    assert "Authorization" not in h.last.headers


def test_login_stores_token_and_client_id(h: Harness) -> None:
    h.respond(json_body=TOKEN_BODY)
    tok, client = h.with_client(lambda c: c.auth.login("user@x", "pw", "client-1"))
    assert tok.access_token == "new-access"
    assert client.token == "new-access"
    assert client.client_id == "client-1"
    assert h.last.method == "POST"
    assert h.path() == "/auth_token"
    assert "Authorization" not in h.last.headers
    assert h.body() == {
        "grant_type": "password",
        "username": "user@x",
        "password": "pw",
        "client_id": "client-1",
    }


def test_refresh_uses_stored_client_id(h: Harness) -> None:
    h.client_id = "client-9"
    h.respond(json_body=TOKEN_BODY)
    _, client = h.with_client(lambda c: c.auth.refresh("refresh-1"))
    assert client.token == "new-access"
    assert h.body() == {
        "grant_type": "refresh_token",
        "refresh_token": "refresh-1",
        "client_id": "client-9",
    }


def test_login_sso(h: Harness) -> None:
    h.respond(json_body=TOKEN_BODY)
    _, client = h.with_client(
        lambda c: c.auth.login_sso(SSOProviderName.AZURE, "code-1", "client-1", SSOAppTarget.WEB)
    )
    assert client.client_id == "client-1"
    assert h.body() == {
        "grant_type": "sso_auth_code",
        "provider_name": "azure-open-id-connect",
        "auth_code": "code-1",
        "client_id": "client-1",
        "app_target": "web",
    }


def test_login_sso_omits_app_target(h: Harness) -> None:
    h.respond(json_body=TOKEN_BODY)
    h.call(lambda c: c.auth.login_sso(SSOProviderName.GOOGLE, "code", "cid"))
    assert "app_target" not in h.body()


def test_login_failure_keeps_old_token(h: Harness) -> None:
    h.respond(403, json_body={"detail": "Banned"})
    with pytest.raises(APIError) as info:
        h.call(lambda c: c.auth.login("u", "p", "c"))
    assert info.value.is_forbidden


def test_revoke_tokens_keeps_local_token(h: Harness) -> None:
    h.respond(204)
    _, client = h.with_client(lambda c: c.auth.revoke_tokens())
    assert h.last.method == "DELETE"
    assert h.path() == "/auth_token"
    assert h.last.headers["Authorization"] == "Bearer test-token"
    assert client.token == "test-token"


def test_with_credentials() -> None:
    import asyncio

    import httpx

    from seventhings import AsyncClient, Client

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=TOKEN_BODY)

    c = Client.with_credentials(
        "https://x",
        "u",
        "p",
        "cid",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert (c.token, c.client_id) == ("new-access", "cid")

    async def run() -> AsyncClient:
        return await AsyncClient.with_credentials(
            "https://x",
            "u",
            "p",
            "cid",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

    ac = asyncio.run(run())
    assert ac.token == "new-access"
