from __future__ import annotations

import asyncio

import httpx
import pytest

from seventhings import APIError, AsyncClient, Client, DecodeError, NetworkError
from seventhings._operations import (
    int_from_location_id,
    unwrap_resource_fields,
    uuid_from_location,
)
from seventhings._transport import Response

from .conftest import BASE, TOKEN, Harness


def _resp(headers: dict[str, str]) -> Response:
    return Response(201, httpx.Headers(headers), b"")


def test_base_url_trims_trailing_slashes() -> None:
    assert Client("https://x.example///").base_url == "https://x.example/customer-api/v1"
    assert AsyncClient("https://x.example").base_url == "https://x.example/customer-api/v1"


def test_json_request_headers(h: Harness) -> None:
    h.respond(json_body={"a": 1})
    h.call(lambda c: c.objects.get("u1"))
    assert h.last.method == "GET"
    assert h.last.headers["Accept"] == "application/json"
    assert h.last.headers["Authorization"] == f"Bearer {TOKEN}"
    assert "Content-Type" not in h.last.headers


def test_no_authorization_header_without_token(h: Harness) -> None:
    h.token = None
    h.respond(json_body={})
    h.call(lambda c: c.objects.get("u1"))
    assert "Authorization" not in h.last.headers


def test_body_sets_json_content_type(h: Harness) -> None:
    h.respond(201, headers={"Location": "/customer-api/v1/object/new-uuid"})
    uuid = h.call(lambda c: c.objects.create({"name": "Chair"}))
    assert uuid == "new-uuid"
    assert h.last.headers["Content-Type"] == "application/json"
    assert h.body() == {"name": "Chair"}


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 429, 500, 503])
def test_api_error(h: Harness, status: int) -> None:
    h.respond(status, content=b'{"message":"nope"}')
    with pytest.raises(APIError) as info:
        h.call(lambda c: c.objects.get("u1"))
    err = info.value
    assert err.status_code == status
    assert err.body == '{"message":"nope"}'
    assert str(err).startswith(f"seventhings API error {status} ({status} ")
    assert err.is_status_code(status)
    assert err.is_not_found == (status == 404)
    assert err.is_unauthorized == (status == 401)
    assert err.is_forbidden == (status == 403)
    assert err.is_conflict == (status == 409)
    assert err.is_rate_limited == (status == 429)
    assert err.is_server_error == (status >= 500)


def test_feature_inactive() -> None:
    body = '{"message":"The required feature for this endpoint is not active"}'
    assert APIError(403, "403 Forbidden", body).is_feature_inactive
    assert not APIError(404, "404 Not Found", body).is_feature_inactive
    assert not APIError(403, "403 Forbidden", '{"message":"other"}').is_feature_inactive
    assert not APIError(403, "403 Forbidden", "not json").is_feature_inactive


def test_network_error_wraps_transport_errors() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with (
        Client(BASE, http_client=httpx.Client(transport=httpx.MockTransport(boom))) as c,
        pytest.raises(NetworkError, match="connection refused"),
    ):
        c.ping()

    async def run() -> None:
        async with AsyncClient(
            BASE, http_client=httpx.AsyncClient(transport=httpx.MockTransport(boom))
        ) as ac:
            await ac.ping()

    with pytest.raises(NetworkError):
        asyncio.run(run())


def test_invalid_json_raises_decode_error(h: Harness) -> None:
    h.respond(content=b"<html>")
    with pytest.raises(DecodeError):
        h.call(lambda c: c.objects.get("u1"))


def test_raw_request(h: Harness) -> None:
    h.respond(json_body={"ok": True})
    resp = h.call(lambda c: c.request("post", "custom/path", query="a=1", json={"x": 1}))
    assert h.last.method == "POST"
    assert h.path() == "/custom/path"
    assert h.query() == "a=1"
    assert h.body() == {"x": 1}
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_owned_http_client_is_closed_but_injected_one_is_not() -> None:
    injected = httpx.Client()
    with Client(BASE, http_client=injected):
        pass
    assert not injected.is_closed
    injected.close()

    c = Client(BASE)
    c.close()
    assert c._http.is_closed


def test_default_timeout() -> None:
    c = Client(BASE)
    assert c._http.timeout == httpx.Timeout(30.0)
    c.close()
    c = Client(BASE, timeout=None)
    assert c._http.timeout == httpx.Timeout(None)
    c.close()


# -- header helpers ----------------------------------------------------------


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("/customer-api/v1/object/abc-123", "abc-123"),
        ("https://x.example/customer-api/v1/room/r-1", "r-1"),
        ("/customer-api/v1/object/abc-123/", "abc-123"),
        ("abc", "abc"),
    ],
)
def test_uuid_from_location(location: str, expected: str) -> None:
    assert uuid_from_location(_resp({"Location": location})) == expected


@pytest.mark.parametrize("headers", [{}, {"Location": "/"}, {"Location": ""}])
def test_uuid_from_location_errors(headers: dict[str, str]) -> None:
    with pytest.raises(DecodeError):
        uuid_from_location(_resp(headers))


def test_int_from_location_id() -> None:
    assert int_from_location_id(_resp({"Location-Id": "42"})) == 42
    with pytest.raises(DecodeError):
        int_from_location_id(_resp({}))
    with pytest.raises(DecodeError):
        int_from_location_id(_resp({"Location-Id": "abc"}))


def test_unwrap_resource_fields() -> None:
    assert unwrap_resource_fields({"uuid": "u", "fields": {"name": "A"}}) == {
        "name": "A",
        "uuid": "u",
    }
    # An inner uuid wins over the envelope uuid.
    assert unwrap_resource_fields({"uuid": "u", "fields": {"uuid": "inner"}}) == {"uuid": "inner"}
    flat = {"uuid": "u", "name": "A"}
    assert unwrap_resource_fields(flat) is flat
    # Not an envelope unless uuid is a string and fields an object.
    odd = {"uuid": 5, "fields": {"a": 1}}
    assert unwrap_resource_fields(odd) is odd
    odd2 = {"uuid": "u", "fields": "x"}
    assert unwrap_resource_fields(odd2) is odd2
