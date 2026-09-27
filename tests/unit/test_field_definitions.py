from __future__ import annotations

from typing import Any

from seventhings.models import (
    AssetTrackingTemplate,
    CreateFieldDefinition,
    FieldDefinitionFieldType,
    FieldTypeName,
    UpdateFieldDefinition,
)

from .conftest import Harness


def _def(key: str, mandatory: str | None = None, **extra: Any) -> dict[str, Any]:
    attrs = [{"type": "mandatory", "value": mandatory}] if mandatory else []
    return {
        "uuid": f"fd-{key}",
        "field_key": key,
        "field_type": {"name": "TEXT", "constraints": []},
        "label": key.title(),
        "attributes": attrs,
        **extra,
    }


DEFS = [
    _def("name", "yes"),
    _def("serial", "yes"),
    _def("notes", "no"),
    _def("comment"),
    _def("uuid", "yes"),  # system managed
    _def("created_at", "yes"),  # system managed
]


def test_list_is_a_bare_array(h: Harness) -> None:
    h.respond(json_body=DEFS)
    defs = h.call(lambda c: c.field_definitions.list(AssetTrackingTemplate.ASSET))
    assert [d.field_key for d in defs] == [d["field_key"] for d in DEFS]
    assert h.path() == "/asset-tracking/asset/field-definitions"


def test_get_create_update(h: Harness) -> None:
    ft = FieldDefinitionFieldType(FieldTypeName.TEXT)
    h.respond(json_body=_def("name", "yes"))
    h.respond(201, headers={"Location": "/asset-tracking/room/field-definition/fd-9"})
    h.respond(204)
    fd = h.call(lambda c: c.field_definitions.get(AssetTrackingTemplate.PERSON, "fd-name"))
    assert fd.is_mandatory()
    new = CreateFieldDefinition(field_type=ft, label="Size")
    assert h.call(lambda c: c.field_definitions.create("room", new)) == "fd-9"
    upd = UpdateFieldDefinition(uuid="fd-9", field_key="size", field_type=ft, label="Size")
    h.call(lambda c: c.field_definitions.update(AssetTrackingTemplate.ROOM, "fd-9", upd))
    assert [(r.method, h.path(i)) for i, r in enumerate(h.requests)] == [
        ("GET", "/asset-tracking/person/field-definition/fd-name"),
        ("POST", "/asset-tracking/room/field-definition"),
        ("PUT", "/asset-tracking/room/field-definition/fd-9"),
    ]
    assert h.body(1)["label"] == "Size"
    assert h.body(2)["field_key"] == "size"


def test_mandatory_excludes_system_managed(h: Harness) -> None:
    h.respond(json_body=DEFS)
    defs = h.call(lambda c: c.field_definitions.mandatory(AssetTrackingTemplate.ASSET))
    assert [d.field_key for d in defs] == ["name", "serial"]


def test_missing_mandatory_fields(h: Harness) -> None:
    h.respond(json_body=DEFS)
    missing = h.call(
        lambda c: c.field_definitions.missing_mandatory_fields(
            AssetTrackingTemplate.ASSET, {"name": "Chair", "serial": None, "notes": "x"}
        )
    )
    assert missing == ["serial"]
    assert len(h.requests) == 1
