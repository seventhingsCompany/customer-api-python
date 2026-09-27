"""List options and their query-string encodings.

The API expects deep-object style query parameters such as
``sort[name]=ASC&filter[status][in][]=a``. Brackets and field names are sent
literally; only values are escaped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus

from .enums import (
    FilterOperator,
    SortDirection,
    TaskReferenceType,
    TaskStatus,
    UserSortBy,
    UserSortOrder,
)

_MULTI_VALUE_OPS = frozenset(
    {FilterOperator.LIKE, FilterOperator.NOT_LIKE, FilterOperator.IN, FilterOperator.NIN}
)


def _q(value: Any) -> str:
    return quote_plus(str(value), safe="")


@dataclass(frozen=True, slots=True)
class FilterEntry:
    field: str
    operator: FilterOperator
    values: tuple[str, ...]


def eq(field: str, value: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.EQ, (value,))


def neq(field: str, value: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.NEQ, (value,))


def gt(field: str, value: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.GT, (value,))


def gt_or_null(field: str, value: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.GT_OR_NULL, (value,))


def gte(field: str, value: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.GTE, (value,))


def gte_or_null(field: str, value: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.GTE_OR_NULL, (value,))


def lt(field: str, value: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.LT, (value,))


def lt_or_null(field: str, value: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.LT_OR_NULL, (value,))


def lte(field: str, value: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.LTE, (value,))


def lte_or_null(field: str, value: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.LTE_OR_NULL, (value,))


def like(field: str, value: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.LIKE, (value,))


def not_like(field: str, value: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.NOT_LIKE, (value,))


def in_(field: str, *values: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.IN, values)


def nin(field: str, *values: str) -> FilterEntry:
    return FilterEntry(field, FilterOperator.NIN, values)


@dataclass(slots=True)
class ListOptions:
    """Paging, sorting and filtering for objects, rooms, locations, rentals and hub lists.

    Build fluently::

        ListOptions().with_per_page(50).sort_by("name", SortDirection.ASC).where(eq("status", "x"))
    """

    page: int | None = None
    per_page: int | None = None
    sort: dict[str, SortDirection] = field(default_factory=dict)
    filters: list[FilterEntry] = field(default_factory=list)

    def with_page(self, page: int) -> ListOptions:
        self.page = page
        return self

    def with_per_page(self, per_page: int) -> ListOptions:
        self.per_page = per_page
        return self

    def sort_by(self, field: str, direction: SortDirection = SortDirection.ASC) -> ListOptions:
        self.sort[field] = direction
        return self

    def where(self, *filters: FilterEntry) -> ListOptions:
        self.filters.extend(filters)
        return self

    def encode(self) -> str:
        parts: list[str] = []
        if self.page:
            parts.append(f"page={self.page}")
        if self.per_page:
            parts.append(f"per_page={self.per_page}")
        for name, direction in self.sort.items():
            parts.append(f"sort[{name}]={_q(SortDirection(direction).value)}")
        for f in self.filters:
            op = FilterOperator(f.operator).value
            if f.operator in _MULTI_VALUE_OPS:
                parts.extend(f"filter[{f.field}][{op}][]={_q(v)}" for v in f.values)
            else:
                value = f.values[0] if f.values else ""
                parts.append(f"filter[{f.field}][{op}]={_q(value)}")
        return "&".join(parts)


@dataclass(slots=True)
class UserListOptions:
    page: int | None = None
    per_page: int | None = None
    sort_by: UserSortBy | None = None
    order: UserSortOrder | None = None

    def encode(self) -> str:
        return _encode_pairs(
            ("page", self.page),
            ("per_page", self.per_page),
            ("sort_by", self.sort_by),
            ("order", self.order),
        )


@dataclass(slots=True)
class PersonListOptions:
    """Paging and sorting for persons. ``sort_by`` is any person field key."""

    page: int | None = None
    per_page: int | None = None
    sort_by: str | None = None
    order: UserSortOrder | None = None

    def encode(self) -> str:
        return _encode_pairs(
            ("page", self.page),
            ("per_page", self.per_page),
            ("sort_by", self.sort_by),
            ("order", self.order),
        )


@dataclass(slots=True)
class TaskListOptions:
    status: TaskStatus | None = None
    deadline_from: str | None = None
    deadline_to: str | None = None
    assignee: str | None = None
    author: str | None = None
    reference_type: TaskReferenceType | None = None

    def encode(self) -> str:
        return _encode_pairs(
            ("status", self.status),
            ("deadline_from", self.deadline_from),
            ("deadline_to", self.deadline_to),
            ("assignee", self.assignee),
            ("author", self.author),
            ("reference_type", self.reference_type),
        )


@dataclass(slots=True)
class HistoryListOptions:
    """Paging for history endpoints. The API defaults to page 1, 50 per page (max 200)."""

    page: int | None = None
    per_page: int | None = None

    def encode(self) -> str:
        return _encode_pairs(
            ("page", self.page or None),
            ("per_page", self.per_page or None),
        )


def _encode_pairs(*pairs: tuple[str, Any]) -> str:
    return "&".join(
        f"{key}={_q(value.value if hasattr(value, 'value') else value)}"
        for key, value in pairs
        if value is not None
    )
