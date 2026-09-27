from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from seventhings import DecodeError
from seventhings.models import (
    AddObjectEntry,
    CircularityHubOrder,
    CreateFieldDefinition,
    CreateRentalCase,
    CreateReport,
    CreateTask,
    FieldAttribute,
    FieldDefinition,
    FieldDefinitionFieldType,
    FieldRelation,
    Fields,
    FieldTypeName,
    FieldValueConstraint,
    FileAttachment,
    FilterObject,
    FilterOperator,
    Person,
    PersonListResponse,
    RentalCase,
    RentalCaseReferenceInput,
    RentalCaseRenter,
    RentalCaseStatus,
    RenterType,
    SortDirection,
    Task,
    TaskReferenceInput,
    TaskStatus,
    TimeInterval,
    TimeIntervalUnit,
    TokenResponse,
    UpdateFieldDefinition,
    UpdateTask,
    User,
)

# -- Person ------------------------------------------------------------------


def test_person_preserves_custom_fields() -> None:
    p = Person.from_dict(
        {
            "person_uuid": "p-1",
            "id": 7,
            "email": "a@b.com",
            "first_name": "Ada",
            "cost_center": "CC-100",
            "employee_number": 4242,
        }
    )
    assert (p.uuid, p.id, p.email, p.firstname) == ("p-1", 7, "a@b.com", "Ada")
    assert p.fields.get_str("person_uuid") == "p-1"
    assert p.fields.get_str("cost_center") == "CC-100"
    assert p.fields.get_int("employee_number") == 4242


@pytest.mark.parametrize(
    ("body", "want"),
    [
        ({"person_uuid": "legacy", "custom": "value"}, "legacy"),
        ({"uuid": "current", "custom": "value"}, "current"),
        ({"person_uuid": "legacy", "uuid": "current"}, "legacy"),
        ({"person_uuid": "", "uuid": "current"}, "current"),
        ({"person_uuid": None, "uuid": "current"}, "current"),
        ({}, ""),
    ],
)
def test_person_uuid_compatibility(body: dict[str, Any], want: str) -> None:
    p = Person.from_dict(body)
    assert p.uuid == want
    assert p.fields == body


@pytest.mark.parametrize(
    "body", [{"uuid": 42}, {"person_uuid": 42}, {"uuid": "p-1", "fields": "nope"}, []]
)
def test_person_rejects_invalid_shapes(body: Any) -> None:
    with pytest.raises(DecodeError):
        Person.from_dict(body)


@pytest.mark.parametrize("with_inner_uuid", [True, False])
def test_person_wrapped_response(with_inner_uuid: bool) -> None:
    inner: dict[str, Any] = {
        "id": 7,
        "email": "ada@example.test",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "department": "IT",
        "cost_center": "CC-1",
        "documents": [{"uuid": "file-1"}],
    }
    if with_inner_uuid:
        inner["person_uuid"] = "p-1"
    p = Person.from_dict({"uuid": "p-1", "fields": inner})
    assert p.uuid == "p-1"
    assert (p.id, p.firstname, p.lastname, p.department) == (7, "Ada", "Lovelace", "IT")
    assert p.documents == [{"uuid": "file-1"}]
    # The raw map is the inner map; the envelope uuid is not injected.
    assert p.fields == inner


def test_person_null_fields_is_not_an_envelope() -> None:
    p = Person.from_dict({"uuid": "p-1", "fields": None, "email": "x@y"})
    assert p.uuid == "p-1"
    assert p.email == "x@y"


def test_person_list_response() -> None:
    resp = PersonListResponse.from_dict(
        {
            "items": [
                {"person_uuid": "p-1", "id": 1, "cost_center": "CC-1"},
                {"uuid": "p-2", "id": 2},
            ],
            "page": 1,
            "per_page": 50,
            "sort_by": "id",
            "order": "asc",
            "total": 2,
        }
    )
    assert [p.uuid for p in resp.items] == ["p-1", "p-2"]
    assert resp.items[0].fields["cost_center"] == "CC-1"
    assert (resp.page, resp.per_page, resp.total, resp.sort_by, resp.order) == (
        1,
        50,
        2,
        "id",
        "asc",
    )


# -- Fields ------------------------------------------------------------------


def test_fields_accessors() -> None:
    f = Fields(
        {
            "uuid": "u",
            "name": "Chair",
            "count": 3,
            "whole": 4.0,
            "frac": 1.5,
            "flag": True,
            "nothing": None,
        }
    )
    assert f.uuid == "u" and f.name == "Chair"
    assert f.get_str("name") == "Chair" and f.get_str("count") is None
    assert f.get_int("count") == 3
    assert f.get_int("whole") == 4
    assert f.get_int("frac") is None
    assert f.get_int("flag") is None
    assert f.get_float("count") == 3.0 and f.get_float("frac") == 1.5
    assert f.get_float("flag") is None
    assert f.get_bool("flag") is True and f.get_bool("count") is None
    assert f.has("name") and not f.has("nothing") and not f.has("missing")
    assert Fields().uuid == "" and Fields().name == ""
    assert isinstance(f, dict)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-03-04", datetime(2026, 3, 4, tzinfo=timezone.utc)),
        ("2026-03-04 05:06:07", datetime(2026, 3, 4, 5, 6, 7, tzinfo=timezone.utc)),
        ("2026-03-04T05:06:07Z", datetime(2026, 3, 4, 5, 6, 7, tzinfo=timezone.utc)),
        (
            "2026-03-04T05:06:07+02:00",
            datetime(2026, 3, 4, 3, 6, 7, tzinfo=timezone.utc),
        ),
    ],
)
def test_fields_time(value: str, expected: datetime) -> None:
    assert Fields({"t": value}).get_time("t") == expected


@pytest.mark.parametrize("value", ["", "yesterday", 5, None, "2026-03-04T05:06:07"])
def test_fields_time_invalid(value: Any) -> None:
    assert Fields({"t": value}).get_time("t") is None


# -- enums -------------------------------------------------------------------


def test_enums_compare_to_wire_values_and_decode_leniently() -> None:
    assert TaskStatus.OPEN.value == "open" and TaskStatus("open") is TaskStatus.OPEN
    assert str(SortDirection.ASC) == "ASC"
    task = Task.from_dict({"uuid": "t", "status": "some_future_status"})
    assert task.status == "some_future_status"
    assert Task.from_dict({"status": "closed"}).status is TaskStatus.CLOSED


# -- response models ---------------------------------------------------------


def test_token_response() -> None:
    tok = TokenResponse.from_dict(
        {
            "access_token": "a",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": None,
            "refresh_token": "r",
            "user_id": 9,
        }
    )
    assert tok == TokenResponse("a", 3600, "Bearer", None, "r", 9)


def test_user_decodes_display_name() -> None:
    u = User.from_dict({"uuid": "u", "id": 1, "email": "e", "display_name": "E"})
    assert u.display_name == "E" and u.firstname is None


def test_task_decoding() -> None:
    task = Task.from_dict(
        {
            "uuid": "t-1",
            "title": "Check",
            "status": "open",
            "deadline": "2026-01-01 00:00:00",
            "assignees": ["u1"],
            "author": "u2",
            "references": [{"type": "asset", "uuid": "a1", "name": "A", "id": 3, "status": "done"}],
            "reminders": [{"unit": "days", "value": 2}],
            "recurring_schedule": {"unit": "weeks", "value": 1},
            "comment": None,
            "attachments": [{"uuid": "f", "name": "n", "type": "image/png", "size": 10}],
            "created_at": "c",
            "updated_at": "u",
        }
    )
    assert task.references[0].status == "done"
    assert task.reminders == [TimeInterval(TimeIntervalUnit.DAYS, 2)]
    assert task.recurring_schedule == TimeInterval(TimeIntervalUnit.WEEKS, 1)
    assert task.attachments[0].size == 10


def test_rental_case_decoding() -> None:
    rc = RentalCase.from_dict(
        {
            "uuid": "r",
            "status": "borrowed",
            "title": "Laptop",
            "renter": {"type": "user", "value": "u1"},
            "references": [{"type": "asset", "uuid": "a", "name": "A", "id": 1}],
            "due_date_reminder": {"unit": "days", "value": 1},
        }
    )
    assert rc.status is RentalCaseStatus.BORROWED
    assert rc.renter == RentalCaseRenter(RenterType.USER, "u1")
    assert rc.issue_date_reminder is None
    assert rc.due_date_reminder == TimeInterval(TimeIntervalUnit.DAYS, 1)
    assert RentalCase.from_dict({"renter": None}).renter is None


def test_circularity_hub_order_decoding() -> None:
    order = CircularityHubOrder.from_dict(
        {
            "id": 5,
            "order_number": "O-5",
            "total_price": "12.50",
            "completed": False,
            "billing_data": {"first_name": "A", "zip_code": "123"},
            "articles": [{"id": 1}],
        }
    )
    assert order.total_price == 12.5
    assert order.billing_data is not None and order.billing_data.zip_code == "123"
    assert CircularityHubOrder.from_dict({"total_price": None}).total_price is None


# -- request models ----------------------------------------------------------


def test_create_task_to_dict_minimal() -> None:
    assert CreateTask(title="T").to_dict() == {
        "title": "T",
        "deadline": None,
        "assignees": [],
        "references": [],
        "reminders": [],
        "recurring_schedule": None,
    }


def test_update_task_to_dict_full() -> None:
    body = UpdateTask(
        title="T",
        deadline="2026-01-01",
        assignees=["u"],
        references=[TaskReferenceInput("a1")],
        reminders=[TimeInterval(TimeIntervalUnit.DAYS, 1)],
        recurring_schedule=TimeInterval(TimeIntervalUnit.MONTHS, 1),
        comment="c",
        attachments=["f1"],
        notify=False,
    ).to_dict()
    assert body["references"] == [{"type": "asset", "uuid": "a1"}]
    assert body["reminders"] == [{"unit": "days", "value": 1}]
    assert body["recurring_schedule"] == {"unit": "months", "value": 1}
    assert (body["comment"], body["attachments"], body["notify"]) == ("c", ["f1"], False)


def test_create_rental_case_to_dict() -> None:
    rc = CreateRentalCase(
        title="R",
        renter=RentalCaseRenter(RenterType.PLAIN, "Bob"),
        issue_date="2026-01-01 00:00:00",
        due_date="2026-01-08 00:00:00",
        responsible_user_uuid="u1",
        references=[RentalCaseReferenceInput("a1")],
    )
    assert rc.to_dict() == {
        "title": "R",
        "renter": {"type": "plain", "value": "Bob"},
        "references": [{"type": "asset", "uuid": "a1"}],
        "issue_date": "2026-01-01 00:00:00",
        "due_date": "2026-01-08 00:00:00",
        "comment": "",
        "responsible_user_uuid": "u1",
        "attachments": [],
    }
    with_reminder = CreateRentalCase(
        title="R",
        renter=None,
        issue_date="i",
        due_date="d",
        responsible_user_uuid="u",
        due_date_reminder=TimeInterval(TimeIntervalUnit.DAYS, 1),
    ).to_dict()
    assert with_reminder["renter"] is None
    assert with_reminder["due_date_reminder"] == {"unit": "days", "value": 1}
    assert "issue_date_reminder" not in with_reminder


def test_field_definition_request_bodies() -> None:
    ft = FieldDefinitionFieldType(
        FieldTypeName.DROPDOWN, [FieldValueConstraint("allowed_values", ["a", "b"])]
    )
    create = CreateFieldDefinition(
        field_type=ft,
        label="Color",
        attributes=[FieldAttribute("mandatory", "yes")],
        relations=[FieldRelation("show_if", "f-1")],
    ).to_dict()
    assert create == {
        "field_type": {
            "name": "DROPDOWN",
            "constraints": [{"type": "allowed_values", "value": ["a", "b"]}],
        },
        "label": "Color",
        "attributes": [{"type": "mandatory", "value": "yes"}],
        "relations": [{"type": "show_if", "field_uuid": "f-1"}],
        "comment": None,
        "default_value": None,
        "possible_values": [],
    }
    update = UpdateFieldDefinition(uuid="u", field_key="color", field_type=ft, label="C")
    assert update.to_dict()["uuid"] == "u"
    assert update.to_dict()["field_key"] == "color"


def test_field_definition_helpers() -> None:
    fd = FieldDefinition.from_dict(
        {
            "uuid": "u",
            "field_key": "color",
            "field_type": {
                "name": "DROPDOWN",
                "constraints": [{"type": "allowed_values", "value": ["red", "blue"]}],
            },
            "label": "Color",
            "attributes": [{"type": "mandatory", "value": "yes"}, {"type": "unique", "value": 1}],
            "relations": [{"type": "r", "field_uuid": "x", "comparison_values": [1]}],
        }
    )
    assert fd.is_mandatory()
    assert fd.has_attribute("unique") and not fd.has_attribute("hidden")
    assert fd.attribute("unique") == 1 and fd.attribute("hidden") is None
    assert fd.field_type.allowed_values() == ["red", "blue"]
    assert fd.relations[0].comparison_values == [1]
    assert UpdateFieldDefinition.from_definition(fd).field_key == "color"

    not_mandatory = FieldDefinition.from_dict(
        {"attributes": [{"type": "mandatory", "value": "no"}], "field_type": {"name": "TEXT"}}
    )
    assert not not_mandatory.is_mandatory()
    assert not_mandatory.field_type.allowed_values() is None


def test_small_request_models() -> None:
    assert FileAttachment("photos", "f-1").to_dict() == {"field-key": "photos", "file-uuid": "f-1"}
    assert AddObjectEntry("chairs", "10.00").to_dict() == {"category": "chairs", "price": "10.00"}
    assert CreateReport("t", ["a"]).to_dict() == {
        "report_template_uuid": "t",
        "object_uuids": ["a"],
    }
    assert FilterObject().to_dict() == {}
    assert FilterObject(
        filter={"name": {FilterOperator.LIKE: "x"}}, sort={"name": SortDirection.ASC}
    ).to_dict() == {"filter": {"name": {"like": "x"}}, "sort": {"name": "ASC"}}
