from __future__ import annotations

from seventhings.models import (
    CreateReport,
    Fields,
    ListOptions,
    PersonListOptions,
    SortDirection,
    UserListOptions,
    eq,
)

from .conftest import Harness


def test_report_templates(h: Harness) -> None:
    h.respond(json_body=[{"uuid": "rt-1", "name": "Inventory"}])
    templates = h.call(lambda c: c.reports.list_templates())
    assert templates[0].name == "Inventory"
    assert h.path() == "/report-template"


def test_report_create_returns_pdf_bytes(h: Harness) -> None:
    h.respond(content=b"%PDF-1.7 ...", headers={"Content-Type": "application/pdf"})
    pdf = h.call(lambda c: c.reports.create(CreateReport("rt-1", ["o-1", "o-2"])))
    assert pdf.startswith(b"%PDF-")
    assert (h.last.method, h.path()) == ("POST", "/report")
    assert h.last.headers["Accept"] == "application/pdf"
    assert h.body() == {"report_template_uuid": "rt-1", "object_uuids": ["o-1", "o-2"]}


# -- pagination ----------------------------------------------------------------


def _page(n: int, start: int = 0) -> dict[str, list[dict[str, str]]]:
    return {"items": [{"uuid": f"o-{start + i}"} for i in range(n)]}


def test_objects_all_walks_until_short_page(h: Harness) -> None:
    h.respond(json_body=_page(2)).respond(json_body=_page(2, 2)).respond(json_body=_page(1, 4))
    opts = ListOptions(page=9, per_page=2).sort_by("name", SortDirection.ASC).where(eq("a", "b"))
    items = h.collect(lambda c: c.objects.all(opts))
    assert [i.uuid for i in items] == ["o-0", "o-1", "o-2", "o-3", "o-4"]
    assert all(isinstance(i, Fields) for i in items)
    assert [h.query(i) for i in range(3)] == [
        f"page={p}&per_page=2&sort[name]=ASC&filter[a][eq]=b" for p in (1, 2, 3)
    ]
    # The caller's options are untouched.
    assert (opts.page, opts.per_page) == (9, 2)


def test_all_stops_on_empty_page(h: Harness) -> None:
    h.respond(json_body=_page(2)).respond(json_body=_page(0))
    items = h.collect(lambda c: c.rooms.all(ListOptions(per_page=2)))
    assert len(items) == 2
    assert len(h.requests) == 2


def test_all_defaults_to_page_size_100(h: Harness) -> None:
    h.respond(json_body=_page(3))
    assert len(h.collect(lambda c: c.locations.all())) == 3
    assert h.query() == "page=1&per_page=100"


def test_all_can_stop_early(h: Harness) -> None:
    h.respond(json_body=_page(2)).respond(json_body=_page(2, 2))

    def first_three(c: object) -> object:
        it = c.objects.all(ListOptions(per_page=2))  # type: ignore[attr-defined]
        if hasattr(it, "__anext__"):

            async def take() -> list[str]:
                out = []
                async for x in it:
                    out.append(x.uuid)
                    if len(out) == 3:
                        break
                return out

            return take()
        out = []
        for x in it:
            out.append(x.uuid)
            if len(out) == 3:
                break
        return out

    assert h.call(first_three) == ["o-0", "o-1", "o-2"]
    assert len(h.requests) == 2


def test_rentals_and_hub_items_all(h: Harness) -> None:
    h.respond(json_body={"items": [{"uuid": "r-1", "status": "requested"}]})
    h.respond(json_body={"items": [{"id": 1}, {"id": 2}]})
    rentals = h.collect(lambda c: c.rentals.all())
    assert rentals[0].uuid == "r-1"
    items = h.collect(lambda c: c.circularity_hub.all_items())
    assert [i.get_int("id") for i in items] == [1, 2]
    assert h.path(0) == "/rental-management/rental-cases"
    assert h.path(1) == "/circularity-hub/items"


def test_users_and_persons_all(h: Harness) -> None:
    listing = {"page": 1, "per_page": 1, "sort_by": "id", "order": "asc", "total": 2}
    h.respond(json_body={"items": [{"uuid": "u-1"}], **listing})
    h.respond(json_body={"items": [], **listing})
    users = h.collect(lambda c: c.users.all(UserListOptions(per_page=1)))
    assert [u.uuid for u in users] == ["u-1"]
    assert [h.query(0), h.query(1)] == ["page=1&per_page=1", "page=2&per_page=1"]

    h.respond(json_body={"items": [{"person_uuid": "p-1"}], **listing})
    persons = h.collect(lambda c: c.persons.all(PersonListOptions(sort_by="email")))
    assert [p.uuid for p in persons] == ["p-1"]
    assert h.query() == "page=1&per_page=100&sort_by=email"
