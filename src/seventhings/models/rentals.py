from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import _decode as d
from .enums import RentalCaseReferenceType, RentalCaseStatus, RenterType
from .files import AttachmentFile
from .tasks import TimeInterval


@dataclass(frozen=True, slots=True)
class RentalCaseRenter:
    """Who rents: a user UUID (``RenterType.USER``) or free text (``RenterType.PLAIN``)."""

    type: RenterType | str
    value: str

    @classmethod
    def from_dict(cls, data: Any) -> RentalCaseRenter:
        m = d.obj(data, "renter")
        return cls(type=d.enum(RenterType, m.get("type")), value=d.string(m.get("value")))

    def to_dict(self) -> dict[str, Any]:
        return {"type": str(self.type), "value": self.value}


@dataclass(frozen=True, slots=True)
class RentalCaseReference:
    type: RentalCaseReferenceType | str
    uuid: str
    name: str
    id: int

    @classmethod
    def from_dict(cls, data: Any) -> RentalCaseReference:
        m = d.obj(data, "rental case reference")
        return cls(
            type=d.enum(RentalCaseReferenceType, m.get("type")),
            uuid=d.string(m.get("uuid")),
            name=d.string(m.get("name")),
            id=d.integer(m.get("id")),
        )


@dataclass(frozen=True, slots=True)
class RentalCaseReferenceInput:
    uuid: str
    type: RentalCaseReferenceType = RentalCaseReferenceType.ASSET

    def to_dict(self) -> dict[str, Any]:
        return {"type": str(self.type), "uuid": self.uuid}


@dataclass(frozen=True, slots=True)
class RentalCase:
    uuid: str
    status: RentalCaseStatus | str
    title: str
    renter: RentalCaseRenter | None
    references: list[RentalCaseReference]
    issue_date: str | None
    issue_date_reminder: TimeInterval | None
    due_date: str | None
    due_date_reminder: TimeInterval | None
    comment: str | None
    responsible_user_uuid: str | None
    author: str | None
    attachments: list[AttachmentFile]
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, data: Any) -> RentalCase:
        m = d.obj(data, "rental case")
        renter = m.get("renter")
        return cls(
            uuid=d.string(m.get("uuid")),
            status=d.enum(RentalCaseStatus, m.get("status")),
            title=d.string(m.get("title")),
            renter=RentalCaseRenter.from_dict(renter) if renter is not None else None,
            references=[
                RentalCaseReference.from_dict(r) for r in d.arr(m.get("references"), "refs")
            ],
            issue_date=d.opt_string(m.get("issue_date")),
            issue_date_reminder=TimeInterval.from_optional(m.get("issue_date_reminder")),
            due_date=d.opt_string(m.get("due_date")),
            due_date_reminder=TimeInterval.from_optional(m.get("due_date_reminder")),
            comment=d.opt_string(m.get("comment")),
            responsible_user_uuid=d.opt_string(m.get("responsible_user_uuid")),
            author=d.opt_string(m.get("author")),
            attachments=[
                AttachmentFile.from_dict(a) for a in d.arr(m.get("attachments"), "attachments")
            ],
            created_at=d.string(m.get("created_at")),
            updated_at=d.string(m.get("updated_at")),
        )


@dataclass(frozen=True, slots=True)
class CreateRentalCase:
    """Request body for creating a rental case. Reminders are sent only when set."""

    title: str
    renter: RentalCaseRenter | None
    issue_date: str
    due_date: str
    responsible_user_uuid: str
    references: list[RentalCaseReferenceInput] = field(default_factory=list)
    comment: str = ""
    attachments: list[str] = field(default_factory=list)
    issue_date_reminder: TimeInterval | None = None
    due_date_reminder: TimeInterval | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "title": self.title,
            "renter": self.renter.to_dict() if self.renter else None,
            "references": [r.to_dict() for r in self.references],
            "issue_date": self.issue_date,
            "due_date": self.due_date,
            "comment": self.comment,
            "responsible_user_uuid": self.responsible_user_uuid,
            "attachments": list(self.attachments),
        }
        if self.issue_date_reminder is not None:
            body["issue_date_reminder"] = self.issue_date_reminder.to_dict()
        if self.due_date_reminder is not None:
            body["due_date_reminder"] = self.due_date_reminder.to_dict()
        return body


@dataclass(frozen=True, slots=True)
class UpdateRentalCase(CreateRentalCase):
    """Request body for replacing a rental case (same shape as CreateRentalCase)."""
