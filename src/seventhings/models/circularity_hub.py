from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import _decode as d
from .enums import FilterOperator, SortDirection


@dataclass(frozen=True, slots=True)
class FilterObject:
    """JSON filter body: ``{"filter": {field: {op: value}}, "sort": {field: dir}}``."""

    filter: dict[str, dict[FilterOperator, Any]] = field(default_factory=dict)
    sort: dict[str, SortDirection] = field(default_factory=dict)

    def filter_dict(self) -> dict[str, dict[str, Any]]:
        return {k: {str(op): v for op, v in ops.items()} for k, ops in self.filter.items()}

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if self.filter:
            body["filter"] = self.filter_dict()
        if self.sort:
            body["sort"] = {k: str(v) for k, v in self.sort.items()}
        return body


@dataclass(frozen=True, slots=True)
class AddObjectEntry:
    category: str
    price: str

    def to_dict(self) -> dict[str, Any]:
        return {"category": self.category, "price": self.price}


@dataclass(frozen=True, slots=True)
class CircularityHubBillingData:
    first_name: str | None = None
    last_name: str | None = None
    street: str | None = None
    house_number: str | None = None
    zip_code: str | None = None
    city: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> CircularityHubBillingData:
        m = d.obj(data, "billing data")
        return cls(
            first_name=d.opt_string(m.get("first_name")),
            last_name=d.opt_string(m.get("last_name")),
            street=d.opt_string(m.get("street")),
            house_number=d.opt_string(m.get("house_number")),
            zip_code=d.opt_string(m.get("zip_code")),
            city=d.opt_string(m.get("city")),
        )


@dataclass(frozen=True, slots=True)
class CircularityHubOrder:
    id: int
    order_number: str
    created_at: str
    user_id: int | None
    total_price: float | None
    completed: bool
    cancelled: bool
    cancellation_reason: str | None
    billing_data: CircularityHubBillingData | None
    articles: list[dict[str, Any]]

    @classmethod
    def from_dict(cls, data: Any) -> CircularityHubOrder:
        m = d.obj(data, "circularity hub order")
        billing = m.get("billing_data")
        return cls(
            id=d.integer(m.get("id")),
            order_number=d.string(m.get("order_number")),
            created_at=d.string(m.get("created_at")),
            user_id=d.opt_integer(m.get("user_id")),
            total_price=d.opt_number(m.get("total_price")),
            completed=d.boolean(m.get("completed")),
            cancelled=d.boolean(m.get("cancelled")),
            cancellation_reason=d.opt_string(m.get("cancellation_reason")),
            billing_data=(
                CircularityHubBillingData.from_dict(billing) if billing is not None else None
            ),
            articles=[a for a in d.arr(m.get("articles"), "articles") if isinstance(a, dict)],
        )
