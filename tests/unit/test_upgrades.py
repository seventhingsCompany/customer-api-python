"""API upgrade (Go v1.5.0): catalog, PKCE, thumbnail sizes, timed rentals, renter guard."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl

import pytest

from seventhings import APIError, RentalCaseRenterRequiredError
from seventhings.models import (
    CatalogItemListResponse,
    CreateRentalCase,
    ListOptions,
    RentalCaseRenter,
    RenterType,
    SortDirection,
    UpdateRentalCase,
)

from .conftest import Harness

FIELDS = {"catalog_object_inventory_name": "Laptop"}
ITEM = {"uuid": "c-1", "fields": FIELDS}


def test_catalog_items_crud(h: Harness) -> None:
    h.respond(
        json_body={"items": [ITEM], "page": 2, "per_page": 10, "total": 11, "sort": {"id": "DESC"}}
    )
    h.respond(json_body=ITEM)
    h.respond(201, headers={"Location-UUID": "c-1"})
    h.respond(204)
    h.respond(204)
    opts = ListOptions(page=2, per_page=10, sort={"id": SortDirection.DESC})
    page = h.call(lambda c: c.catalog_items.list(opts))
    assert (page.page, page.per_page, page.total) == (2, 10, 11)
    assert page.sort == {"id": SortDirection.DESC}
    assert page.items[0].uuid == "c-1" and page.items[0].fields == FIELDS
    item = h.call(lambda c: c.catalog_items.get("c-1"))
    assert (item.uuid, item.fields.get_str("catalog_object_inventory_name")) == ("c-1", "Laptop")
    assert h.call(lambda c: c.catalog_items.create(FIELDS)) == "c-1"
    h.call(lambda c: c.catalog_items.update("c-1", item.fields))
    h.call(lambda c: c.catalog_items.delete("c-1"))
    assert [(r.method, h.path(i)) for i, r in enumerate(h.requests)] == [
        ("GET", "/catalog-items"),
        ("GET", "/catalog-item/c-1"),
        ("POST", "/catalog-item"),
        ("PUT", "/catalog-item/c-1"),
        ("DELETE", "/catalog-item/c-1"),
    ]
    assert ("page", "2") in h.query_pairs(0) and ("sort[id]", "DESC") in h.query_pairs(0)
    assert h.body(2) == h.body(3) == {"fields": FIELDS}


def test_catalog_item_create_location_fallback(h: Harness) -> None:
    h.respond(201, headers={"Location": "/customer-api/v1/catalog-item/c-2"})
    assert h.call(lambda c: c.catalog_items.create({})) == "c-2"
    assert h.body() == {"fields": {}}


def test_catalog_items_all(h: Harness) -> None:
    h.respond(json_body={"items": [ITEM, ITEM], "page": 1, "per_page": 2, "total": 3, "sort": []})
    h.respond(json_body={"items": [ITEM], "page": 2, "per_page": 2, "total": 3, "sort": []})
    items = h.collect(lambda c: c.catalog_items.all(ListOptions(per_page=2)))
    assert len(items) == 3
    assert [h.query(i) for i in range(2)] == ["page=1&per_page=2", "page=2&per_page=2"]


@pytest.mark.parametrize("sort", [[], {}, None, "missing"])
def test_catalog_empty_sorting(sort: Any) -> None:
    data: dict[str, Any] = {"items": []}
    if sort != "missing":
        data["sort"] = sort
    assert CatalogItemListResponse.from_dict(data).sort == {}


@pytest.mark.parametrize("sort", [["id"], 42])
def test_catalog_invalid_sorting(sort: Any) -> None:
    with pytest.raises(ValueError):
        CatalogItemListResponse.from_dict({"sort": sort})


def test_login_authorization_code(h: Harness) -> None:
    h.token = None
    h.respond(json_body={"access_token": "access", "refresh_token": "refresh"})
    tok, client = h.with_client(
        lambda c: c.auth.login_authorization_code(
            "code", "verifier", "https://example.test/callback", "client"
        )
    )
    assert tok.access_token == "access"
    assert (client.token, client.client_id) == ("access", "client")
    req = h.last
    assert (req.method, h.path()) == ("POST", "/auth_token")
    assert req.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert req.headers["Accept"] == "application/json"
    assert "Authorization" not in req.headers
    assert dict(parse_qsl(req.content.decode())) == {
        "grant_type": "authorization_code",
        "code": "code",
        "code_verifier": "verifier",
        "redirect_uri": "https://example.test/callback",
        "client_id": "client",
    }


def test_login_authorization_code_never_sends_token(h: Harness) -> None:
    h.respond(json_body={"access_token": "new"})
    h.call(lambda c: c.auth.login_authorization_code("c", "v", "u", "id"))
    assert "Authorization" not in h.last.headers


def test_thumbnail_with_size(h: Harness) -> None:
    h.respond(content=b"image")
    assert h.call(lambda c: c.files.get_thumbnail("f-1", width=320, height=240)) == b"image"
    assert h.path() == "/file/f-1/thumbnail"
    assert h.query() == "width=320&height=240"
    assert h.last.headers["Accept"] != "application/json"


@pytest.mark.parametrize(
    ("width", "height"),
    [(0, 100), (100, 0), (-1, 100), (2001, 100), (100, 2001), (100, None), (None, 100), (True, 1)],
)
def test_thumbnail_rejects_invalid_size(h: Harness, width: Any, height: Any) -> None:
    with pytest.raises(ValueError):
        h.call(lambda c: c.files.get_thumbnail("f-1", width=width, height=height))
    assert h.requests == []


def test_rental_requires_renter_before_request(h: Harness) -> None:
    create = CreateRentalCase(
        title="R", renter=None, issue_date="i", due_date="d", responsible_user_uuid="u"
    )
    update = UpdateRentalCase(
        title="R", renter=None, issue_date="i", due_date="d", responsible_user_uuid="u"
    )
    with pytest.raises(RentalCaseRenterRequiredError):
        h.call(lambda c: c.rentals.create(create))
    with pytest.raises(RentalCaseRenterRequiredError):
        h.call(lambda c: c.rentals.update("existing", update))
    assert h.requests == []


def test_timed_rental_request_body(h: Harness) -> None:
    h.respond(201, headers={"Location": "/rental-management/rental-case/r-1"})
    create = CreateRentalCase(
        title="R",
        renter=RentalCaseRenter(RenterType.PLAIN, "John"),
        issue_date="2099-01-01",
        due_date="2099-01-01",
        responsible_user_uuid="u",
        is_full_day=False,
        issue_at="2099-01-01T10:00:00+02:00",
        due_at="2099-01-01T12:00:00+02:00",
    )
    assert h.call(lambda c: c.rentals.create(create)) == "r-1"
    body = h.body()
    assert (body["is_full_day"], body["issue_at"], body["due_at"]) == (
        False,
        "2099-01-01T10:00:00+02:00",
        "2099-01-01T12:00:00+02:00",
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.catalog_items.list(),
        lambda c: c.catalog_items.get("c-1"),
        lambda c: c.catalog_items.create({}),
        lambda c: c.catalog_items.update("c-1", {}),
        lambda c: c.catalog_items.delete("c-1"),
        lambda c: c.auth.login_authorization_code("code", "verifier", "uri", "client"),
        lambda c: c.files.get_thumbnail("f-1", width=100, height=100),
    ],
)
def test_upgrade_api_errors(h: Harness, call: Any) -> None:
    h.respond(403, json_body={"message": "not allowed"})
    with pytest.raises(APIError) as info:
        h.call(call)
    assert info.value.is_forbidden
