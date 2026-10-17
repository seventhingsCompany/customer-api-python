from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..errors import DecodeError
from . import _decode as d
from .enums import SortDirection
from .fields import Fields


@dataclass(frozen=True, slots=True)
class CatalogItem:
    """Reusable object master data from the product catalog.

    Object field keys carry a ``catalog_object_`` prefix; catalog metadata such
    as ``id`` has none.
    """

    uuid: str
    fields: Fields = field(default_factory=Fields)

    @classmethod
    def from_dict(cls, data: Any) -> CatalogItem:
        m = d.obj(data, "catalog item")
        raw = m.get("fields")
        return cls(
            uuid=d.string(m.get("uuid")),
            fields=Fields(d.obj(raw, "catalog item fields") if raw is not None else {}),
        )


@dataclass(frozen=True, slots=True)
class CatalogItemListResponse:
    items: list[CatalogItem]
    page: int
    per_page: int
    total: int
    sort: dict[str, SortDirection | str]

    @classmethod
    def from_dict(cls, data: Any) -> CatalogItemListResponse:
        m = d.obj(data, "catalog item list")
        return cls(
            items=[CatalogItem.from_dict(i) for i in d.arr(m.get("items"), "catalog items")],
            page=d.integer(m.get("page")),
            per_page=d.integer(m.get("per_page")),
            total=d.integer(m.get("total")),
            sort=_sort(m.get("sort")),
        )


def _sort(value: Any) -> dict[str, SortDirection | str]:
    # The API sends [] instead of {} when nothing is sorted.
    if value is None or value == []:
        return {}
    if not isinstance(value, dict):
        raise DecodeError(f"expected a JSON object for catalog sort, got {type(value).__name__}")
    return {str(k): d.enum(SortDirection, v) for k, v in value.items()}
