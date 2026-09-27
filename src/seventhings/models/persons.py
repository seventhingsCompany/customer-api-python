from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..errors import DecodeError
from . import _decode as d
from .fields import Fields


@dataclass(frozen=True, slots=True)
class Person:
    """A person record.

    Persons have a tenant-specific schema; the well-known fields are exposed as
    attributes and the complete record is available as ``fields``.
    """

    uuid: str
    id: int
    user_uuid: str
    email: str
    firstname: str | None = None
    lastname: str | None = None
    department: str | None = None
    picture: Any = None
    documents: Any = None
    updated_by_user_id: int | None = None
    updated_at: str | None = None
    created_at: str | None = None
    imported_by_user_id: int | None = None
    imported_with_template_id: int | None = None
    imported_at: str | None = None
    created_on_import_with_template_id: int | None = None
    fields: Fields = field(default_factory=Fields)

    @classmethod
    def from_dict(cls, data: Any) -> Person:
        """Decode a flat person record or a ``{uuid, fields}`` envelope.

        The UUID is taken from ``person_uuid`` and falls back to the top-level ``uuid``.
        """
        m = d.obj(data, "person")
        top_uuid = m.get("uuid")
        if top_uuid is not None and not isinstance(top_uuid, str):
            raise DecodeError("person uuid must be a string")
        src = m
        inner = m.get("fields")
        if top_uuid and inner is not None:
            if not isinstance(inner, dict):
                raise DecodeError("person fields must be a JSON object")
            src = inner
        person_uuid = src.get("person_uuid")
        if person_uuid is not None and not isinstance(person_uuid, str):
            raise DecodeError("person person_uuid must be a string")
        uuid = person_uuid or top_uuid or ""
        return cls(
            uuid=uuid,
            id=d.integer(src.get("id")),
            user_uuid=d.string(src.get("user_uuid")),
            email=d.string(src.get("email")),
            firstname=d.opt_string(src.get("first_name")),
            lastname=d.opt_string(src.get("last_name")),
            department=d.opt_string(src.get("department")),
            picture=src.get("picture"),
            documents=src.get("documents"),
            updated_by_user_id=d.opt_integer(src.get("updated_by_user_id")),
            updated_at=d.opt_string(src.get("updated_at")),
            created_at=d.opt_string(src.get("created_at")),
            imported_by_user_id=d.opt_integer(src.get("imported_by_user_id")),
            imported_with_template_id=d.opt_integer(src.get("imported_with_template_id")),
            imported_at=d.opt_string(src.get("imported_at")),
            created_on_import_with_template_id=d.opt_integer(
                src.get("created_on_import_with_template_id")
            ),
            fields=Fields(src),
        )


@dataclass(frozen=True, slots=True)
class PersonListResponse:
    items: list[Person]
    page: int
    per_page: int
    sort_by: str
    order: str
    total: int

    @classmethod
    def from_dict(cls, data: Any) -> PersonListResponse:
        m = d.obj(data, "person list")
        return cls(
            items=[Person.from_dict(p) for p in d.arr(m.get("items"), "person list items")],
            page=d.integer(m.get("page")),
            per_page=d.integer(m.get("per_page")),
            sort_by=d.string(m.get("sort_by")),
            order=d.string(m.get("order")),
            total=d.integer(m.get("total")),
        )
