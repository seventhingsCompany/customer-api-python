from __future__ import annotations

from seventhings.models import FileAttachment, HistoryListOptions, ListOptions, eq

from .conftest import Harness


def test_list(h: Harness) -> None:
    h.respond(json_body={"items": [{"uuid": "a"}, {"uuid": "b"}]})
    items = h.call(lambda c: c.objects.list(ListOptions(per_page=2).where(eq("status", "x"))))
    assert items == [{"uuid": "a"}, {"uuid": "b"}]
    assert h.path() == "/objects"
    assert h.query() == "per_page=2&filter[status][eq]=x"


def test_list_without_options_has_no_query(h: Harness) -> None:
    h.respond(json_body={"items": []})
    assert h.call(lambda c: c.objects.list()) == []
    assert h.query() == ""


def test_count(h: Harness) -> None:
    h.respond(json_body={"count": 17})
    assert h.call(lambda c: c.objects.count(ListOptions().where(eq("a", "b")))) == 17
    assert h.path() == "/objects/count"
    assert h.query() == "filter[a][eq]=b"


def test_create(h: Harness) -> None:
    h.respond(201, headers={"Location": "https://x/customer-api/v1/object/obj-1"})
    assert h.call(lambda c: c.objects.create({"name": "Desk", "price": 10})) == "obj-1"
    assert h.last.method == "POST"
    assert h.path() == "/object"
    assert h.body() == {"name": "Desk", "price": 10}


def test_get_is_not_unwrapped(h: Harness) -> None:
    raw = {"uuid": "o", "fields": {"name": "x"}}
    h.respond(json_body=raw)
    assert h.call(lambda c: c.objects.get("o")) == raw
    assert h.path() == "/object/o"


def test_get_by_barcode_escapes_segment(h: Harness) -> None:
    h.respond(json_body={"uuid": "o"})
    h.call(lambda c: c.objects.get_by_barcode("INV/100 ?#%"))
    assert h.path() == "/object/by-barcode/INV%2F100%20%3F%23%25"


def test_patch(h: Harness) -> None:
    h.respond(204)
    assert h.call(lambda c: c.objects.patch("o", {"name": "New"})) is None
    assert h.last.method == "PATCH"
    assert h.path() == "/object/o"
    assert h.body() == {"name": "New"}


def test_delete(h: Harness) -> None:
    h.respond(204)
    h.call(lambda c: c.objects.delete("o"))
    assert (h.last.method, h.path()) == ("DELETE", "/object/o")


def test_archive_and_unarchive_send_no_body(h: Harness) -> None:
    h.respond(204).respond(204)
    h.call(lambda c: c.objects.archive("o"))
    h.call(lambda c: c.objects.unarchive("o"))
    assert [(r.method, h.path(i)) for i, r in enumerate(h.requests)] == [
        ("POST", "/object/o/archive"),
        ("POST", "/object/o/unarchive"),
    ]
    for r in h.requests:
        assert r.content == b""
        assert "Content-Type" not in r.headers


def test_add_and_remove_files_return_raw_response(h: Harness) -> None:
    h.respond(207, json_body=[{"status": 200}, {"status": 404}]).respond(200, json_body=[])
    resp = h.call(lambda c: c.objects.add_files("o", [FileAttachment("photos", "f-1")]))
    assert resp.status_code == 207
    assert resp.json() == [{"status": 200}, {"status": 404}]
    assert h.path() == "/object/o/add-file"
    assert h.body() == [{"field-key": "photos", "file-uuid": "f-1"}]

    h.call(lambda c: c.objects.remove_files("o", [FileAttachment("photos", "f-1")]))
    assert h.path() == "/object/o/remove-file"


def test_history(h: Harness) -> None:
    h.respond(
        json_body={
            "items": [{"type": "asset", "event_name": "created"}],
            "page": 2,
            "per_page": 10,
            "total": 11,
        }
    )
    hist = h.call(lambda c: c.objects.history("o", HistoryListOptions(page=2, per_page=10)))
    assert hist.items == [{"type": "asset", "event_name": "created"}]
    assert (hist.page, hist.per_page, hist.total) == (2, 10, 11)
    assert h.path() == "/object/o/history"
    assert h.query() == "page=2&per_page=10"
