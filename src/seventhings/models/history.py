from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from . import _decode as d

T = TypeVar("T")

ObjectHistoryEntry = dict[str, Any]
"""Object history entries vary by ``type`` (asset, task, rental_case, object_merge)."""


@dataclass(frozen=True, slots=True)
class HistoryResponse(Generic[T]):
    items: list[T]
    page: int
    per_page: int
    total: int

    @classmethod
    def from_dict(cls, data: Any, decode_item: Callable[[Any], T]) -> HistoryResponse[T]:
        m = d.obj(data, "history response")
        return cls(
            items=[decode_item(i) for i in d.arr(m.get("items"), "history items")],
            page=d.integer(m.get("page")),
            per_page=d.integer(m.get("per_page")),
            total=d.integer(m.get("total")),
        )


def _common(m: dict[str, Any]) -> dict[str, str]:
    return {
        "user_uuid": d.string(m.get("user_uuid")),
        "occurred_at": d.string(m.get("occurred_at")),
        "event_name": d.string(m.get("event_name")),
        "description": d.string(m.get("description")),
        "details": d.string(m.get("details")),
    }


@dataclass(frozen=True, slots=True)
class RoomHistoryEntry:
    room_uuid: str
    user_uuid: str
    occurred_at: str
    event_name: str
    description: str
    details: str
    """JSON-encoded snapshot, or an empty string."""

    @classmethod
    def from_dict(cls, data: Any) -> RoomHistoryEntry:
        m = d.obj(data, "room history entry")
        return cls(room_uuid=d.string(m.get("room_uuid")), **_common(m))


@dataclass(frozen=True, slots=True)
class LocationHistoryEntry:
    location_uuid: str
    user_uuid: str
    occurred_at: str
    event_name: str
    description: str
    details: str
    """JSON-encoded snapshot, or an empty string."""

    @classmethod
    def from_dict(cls, data: Any) -> LocationHistoryEntry:
        m = d.obj(data, "location history entry")
        return cls(location_uuid=d.string(m.get("location_uuid")), **_common(m))


@dataclass(frozen=True, slots=True)
class PersonHistoryEntry:
    person_uuid: str
    user_uuid: str
    occurred_at: str
    event_name: str
    description: str
    details: str
    """JSON-encoded snapshot, or an empty string."""

    @classmethod
    def from_dict(cls, data: Any) -> PersonHistoryEntry:
        m = d.obj(data, "person history entry")
        return cls(person_uuid=d.string(m.get("person_uuid")), **_common(m))


@dataclass(frozen=True, slots=True)
class TaskHistoryEntry:
    task_uuid: str
    user_uuid: str
    occurred_at: str
    event_name: str
    description: str
    details: str
    """JSON-encoded snapshot, or an empty string."""

    @classmethod
    def from_dict(cls, data: Any) -> TaskHistoryEntry:
        m = d.obj(data, "task history entry")
        return cls(task_uuid=d.string(m.get("task_uuid")), **_common(m))


@dataclass(frozen=True, slots=True)
class RentalCaseHistoryEntry:
    rental_case_uuid: str
    user_uuid: str
    occurred_at: str
    event_name: str
    description: str
    details: str
    """JSON-encoded snapshot, or an empty string."""

    @classmethod
    def from_dict(cls, data: Any) -> RentalCaseHistoryEntry:
        m = d.obj(data, "rental case history entry")
        return cls(rental_case_uuid=d.string(m.get("rental_case_uuid")), **_common(m))
