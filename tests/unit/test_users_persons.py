from __future__ import annotations

from seventhings.models import (
    FilterObject,
    FilterOperator,
    PersonListOptions,
    SortDirection,
    UserListOptions,
    UserSortBy,
    UserSortOrder,
)

from .conftest import Harness

USER = {"uuid": "u-1", "id": 1, "email": "a@b", "firstname": "A", "display_name": "A B"}
LIST = {"page": 1, "per_page": 50, "sort_by": "id", "order": "asc", "total": 1}


def test_users_list(h: Harness) -> None:
    h.respond(json_body={"items": [USER], **LIST})
    resp = h.call(lambda c: c.users.list(UserListOptions(per_page=5, sort_by=UserSortBy.EMAIL)))
    assert resp.items[0].uuid == "u-1" and resp.total == 1
    assert h.path() == "/users"
    assert h.query() == "per_page=5&sort_by=email"


def test_user_get_and_get_by_id(h: Harness) -> None:
    h.respond(json_body=USER).respond(json_body=USER)
    assert h.call(lambda c: c.users.get("u-1")).display_name == "A B"
    assert h.call(lambda c: c.users.get_by_id(1)).email == "a@b"
    assert [h.path(0), h.path(1)] == ["/user/u-1", "/user/by-id/1"]


def test_persons_list_and_count(h: Harness) -> None:
    h.respond(json_body={"items": [{"person_uuid": "p-1", "id": 1}], **LIST})
    h.respond(json_body={"count": 3})
    opts = PersonListOptions(page=1, sort_by="last_name", order=UserSortOrder.DESC)
    resp = h.call(lambda c: c.persons.list(opts))
    assert resp.items[0].uuid == "p-1"
    assert h.path(0) == "/persons"
    assert h.query(0) == "page=1&sort_by=last_name&order=desc"
    assert h.call(lambda c: c.persons.count()) == 3
    assert h.path(1) == "/persons/count"


def test_person_get_wrapped(h: Harness) -> None:
    h.respond(json_body={"uuid": "p-1", "fields": {"id": 7, "email": "e", "cost": "C"}})
    h.respond(json_body={"person_uuid": "p-2", "id": 8})
    p = h.call(lambda c: c.persons.get("p-1"))
    assert (p.uuid, p.id, p.fields["cost"]) == ("p-1", 7, "C")
    assert h.path(0) == "/person/p-1"
    assert h.call(lambda c: c.persons.get_by_id(8)).uuid == "p-2"
    assert h.path(1) == "/person/by-id/8"


def test_person_create_wraps_fields_but_patch_does_not(h: Harness) -> None:
    h.respond(201, headers={"Location": "/customer-api/v1/person/p-9"}).respond(204)
    assert h.call(lambda c: c.persons.create({"email": "x@y"})) == "p-9"
    assert (h.requests[0].method, h.path(0)) == ("POST", "/person")
    assert h.body(0) == {"fields": {"email": "x@y"}}

    h.call(lambda c: c.persons.patch("p-9", {"department": "IT"}))
    assert (h.requests[1].method, h.path(1)) == ("PATCH", "/person/p-9")
    assert h.body(1) == {"department": "IT"}


def test_person_create_with_empty_fields_sends_object(h: Harness) -> None:
    h.respond(201, headers={"Location": "/person/p"})
    h.call(lambda c: c.persons.create({}))
    assert h.last.content == b'{"fields":{}}'


def test_person_delete(h: Harness) -> None:
    h.respond(204)
    h.call(lambda c: c.persons.delete("p-1"))
    assert (h.last.method, h.path()) == ("DELETE", "/person/p-1")


def test_person_create_user_sends_only_filter(h: Harness) -> None:
    h.respond(204)
    f = FilterObject(filter={"email": {FilterOperator.LIKE: "@x"}}, sort={"id": SortDirection.ASC})
    h.call(lambda c: c.persons.create_user(f))
    assert h.path() == "/persons/create-user"
    assert h.body() == {"filter": {"email": {"like": "@x"}}}


def test_person_history(h: Harness) -> None:
    h.respond(json_body={"items": [{"person_uuid": "p-1", "event_name": "e"}], "total": 1})
    hist = h.call(lambda c: c.persons.history("p-1"))
    assert hist.items[0].person_uuid == "p-1"
    assert h.path() == "/person/p-1/history"
