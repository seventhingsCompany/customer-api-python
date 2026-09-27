from __future__ import annotations

import io

import pytest

from seventhings import DecodeError

from .conftest import Harness

FILE = {
    "uuid": "f-1",
    "name": "a.png",
    "type": "image/png",
    "size": 3,
    "creator_id": 2,
    "created_at": "c",
    "data_uri": "/file/f-1/data",
    "thumbnail_uri": "/file/f-1/thumbnail",
}


def test_list_and_get(h: Harness) -> None:
    h.respond(json_body={"items": [FILE]}).respond(json_body=FILE)
    files = h.call(lambda c: c.files.list())
    assert files[0].name == "a.png" and files[0].creator_id == 2
    assert h.path(0) == "/files"
    assert h.call(lambda c: c.files.get("f-1")).size == 3
    assert h.path(1) == "/file/f-1"


def test_upload_multipart_prefers_location_uuid(h: Harness) -> None:
    h.respond(
        201,
        headers={"Location": "/customer-api/v1/file/f-9/data", "Location-UUID": "f-9"},
    )
    assert h.call(lambda c: c.files.upload("a.txt", b"hello")) == "f-9"
    assert (h.last.method, h.path()) == ("POST", "/file")
    ctype = h.last.headers["Content-Type"]
    assert ctype.startswith("multipart/form-data; boundary=")
    assert h.last.headers.get("Accept") != "application/json"
    body = h.last.content
    assert b'name="data"; filename="a.txt"' in body
    assert b"hello" in body


def test_upload_falls_back_to_location(h: Harness) -> None:
    h.respond(201, headers={"Location": "/customer-api/v1/file/f-8"})
    assert h.call(lambda c: c.files.upload("a.txt", io.BytesIO(b"x"))) == "f-8"


def test_upload_without_location_headers_fails(h: Harness) -> None:
    h.respond(201)
    with pytest.raises(DecodeError):
        h.call(lambda c: c.files.upload("a.txt", b"x"))


def test_get_data_and_thumbnail_return_bytes(h: Harness) -> None:
    h.respond(content=b"\x89PNG-data").respond(content=b"thumb")
    assert h.call(lambda c: c.files.get_data("f-1")) == b"\x89PNG-data"
    assert h.path(0) == "/file/f-1/data"
    assert h.requests[0].headers.get("Accept") != "application/json"
    assert h.requests[0].headers["Authorization"] == "Bearer test-token"
    assert h.call(lambda c: c.files.get_thumbnail("f-1")) == b"thumb"
    assert h.path(1) == "/file/f-1/thumbnail"
