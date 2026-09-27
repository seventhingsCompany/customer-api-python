from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import _decode as d


@dataclass(frozen=True, slots=True)
class User:
    uuid: str
    id: int
    email: str
    firstname: str | None = None
    lastname: str | None = None
    display_name: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> User:
        m = d.obj(data, "user")
        return cls(
            uuid=d.string(m.get("uuid")),
            id=d.integer(m.get("id")),
            email=d.string(m.get("email")),
            firstname=d.opt_string(m.get("firstname")),
            lastname=d.opt_string(m.get("lastname")),
            display_name=d.opt_string(m.get("display_name")),
        )


@dataclass(frozen=True, slots=True)
class UserListResponse:
    items: list[User]
    page: int
    per_page: int
    sort_by: str
    order: str
    total: int

    @classmethod
    def from_dict(cls, data: Any) -> UserListResponse:
        m = d.obj(data, "user list")
        return cls(
            items=[User.from_dict(u) for u in d.arr(m.get("items"), "user list items")],
            page=d.integer(m.get("page")),
            per_page=d.integer(m.get("per_page")),
            sort_by=d.string(m.get("sort_by")),
            order=d.string(m.get("order")),
            total=d.integer(m.get("total")),
        )
