from __future__ import annotations

from typing import Any

import pytest

from .conftest import Harness

SERVICES = [("rooms", "room"), ("locations", "location")]

FLAT = {"uuid": "r-1", "name": "Office", "building_id": 3}
WRAPPED = {"uuid": "r-1", "fields": {"name": "Office", "building_id": 3}}
EXPECTED = {"uuid": "r-1", "name": "Office", "building_id": 3}


@pytest.mark.parametrize(("plural", "singular"), SERVICES)
@pytest.mark.parametrize("payload", [FLAT, WRAPPED], ids=["flat", "wrapped"])
def test_list_unwraps(h: Harness, plural: str, singular: str, payload: dict[str, Any]) -> None:
    h.respond(json_body={"items": [payload]})
    assert h.call(lambda c: getattr(c, plural).list()) == [EXPECTED]
    assert h.path() == f"/{plural}"


@pytest.mark.parametrize(("plural", "singular"), SERVICES)
@pytest.mark.parametrize("payload", [FLAT, WRAPPED], ids=["flat", "wrapped"])
def test_get_unwraps(h: Harness, plural: str, singular: str, payload: dict[str, Any]) -> None:
    h.respond(json_body=payload)
    assert h.call(lambda c: getattr(c, plural).get("r-1")) == EXPECTED
    assert h.path() == f"/{singular}/r-1"


@pytest.mark.parametrize(("plural", "singular"), SERVICES)
@pytest.mark.parametrize("payload", [FLAT, WRAPPED], ids=["flat", "wrapped"])
def test_patch_unwraps(h: Harness, plural: str, singular: str, payload: dict[str, Any]) -> None:
    h.respond(json_body=payload)
    assert h.call(lambda c: getattr(c, plural).patch("r-1", {"name": "Office"})) == EXPECTED
    assert (h.last.method, h.path()) == ("PATCH", f"/{singular}/r-1")
    assert h.body() == {"name": "Office"}


@pytest.mark.parametrize(("plural", "singular"), SERVICES)
def test_patch_with_empty_body_returns_none(h: Harness, plural: str, singular: str) -> None:
    h.respond(204)
    assert h.call(lambda c: getattr(c, plural).patch("r-1", {"name": "x"})) is None


@pytest.mark.parametrize(("plural", "singular"), SERVICES)
def test_count_create_delete(h: Harness, plural: str, singular: str) -> None:
    h.respond(json_body={"count": 4})
    h.respond(201, headers={"Location": f"/customer-api/v1/{singular}/new-1"})
    h.respond(204)
    assert h.call(lambda c: getattr(c, plural).count()) == 4
    assert h.call(lambda c: getattr(c, plural).create({"name": "A"})) == "new-1"
    h.call(lambda c: getattr(c, plural).delete("new-1"))
    assert [(r.method, h.path(i)) for i, r in enumerate(h.requests)] == [
        ("GET", f"/{plural}/count"),
        ("POST", f"/{singular}"),
        ("DELETE", f"/{singular}/new-1"),
    ]


@pytest.mark.parametrize(("plural", "singular"), SERVICES)
def test_history(h: Harness, plural: str, singular: str) -> None:
    entry = {
        f"{singular}_uuid": "r-1",
        "user_uuid": "u",
        "occurred_at": "2026-01-01 00:00:00",
        "event_name": "updated",
        "description": "d",
        "details": '{"a":1}',
    }
    h.respond(json_body={"items": [entry], "page": 1, "per_page": 50, "total": 1})
    hist = h.call(lambda c: getattr(c, plural).history("r-1"))
    item = hist.items[0]
    assert getattr(item, f"{singular}_uuid") == "r-1"
    assert (item.event_name, item.details) == ("updated", '{"a":1}')
    assert h.path() == f"/{singular}/r-1/history"
