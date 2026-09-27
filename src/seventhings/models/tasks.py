from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import _decode as d
from .enums import TaskReferenceStatus, TaskReferenceType, TaskStatus, TimeIntervalUnit
from .files import AttachmentFile


@dataclass(frozen=True, slots=True)
class TimeInterval:
    unit: TimeIntervalUnit | str
    value: int

    @classmethod
    def from_dict(cls, data: Any) -> TimeInterval:
        m = d.obj(data, "time interval")
        return cls(unit=d.enum(TimeIntervalUnit, m.get("unit")), value=d.integer(m.get("value")))

    @classmethod
    def from_optional(cls, data: Any) -> TimeInterval | None:
        return None if data is None else cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        return {"unit": str(self.unit), "value": self.value}


@dataclass(frozen=True, slots=True)
class TaskReference:
    type: TaskReferenceType | str
    uuid: str
    name: str
    id: int
    status: TaskReferenceStatus | str

    @classmethod
    def from_dict(cls, data: Any) -> TaskReference:
        m = d.obj(data, "task reference")
        return cls(
            type=d.enum(TaskReferenceType, m.get("type")),
            uuid=d.string(m.get("uuid")),
            name=d.string(m.get("name")),
            id=d.integer(m.get("id")),
            status=d.enum(TaskReferenceStatus, m.get("status")),
        )


@dataclass(frozen=True, slots=True)
class TaskReferenceInput:
    uuid: str
    type: TaskReferenceType = TaskReferenceType.ASSET

    def to_dict(self) -> dict[str, Any]:
        return {"type": str(self.type), "uuid": self.uuid}


@dataclass(frozen=True, slots=True)
class Task:
    uuid: str
    title: str
    status: TaskStatus | str
    deadline: str | None
    assignees: list[str]
    author: str
    references: list[TaskReference]
    reminders: list[TimeInterval]
    recurring_schedule: TimeInterval | None
    comment: str | None
    attachments: list[AttachmentFile]
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, data: Any) -> Task:
        m = d.obj(data, "task")
        return cls(
            uuid=d.string(m.get("uuid")),
            title=d.string(m.get("title")),
            status=d.enum(TaskStatus, m.get("status")),
            deadline=d.opt_string(m.get("deadline")),
            assignees=d.str_list(m.get("assignees")),
            author=d.string(m.get("author")),
            references=[TaskReference.from_dict(r) for r in d.arr(m.get("references"), "refs")],
            reminders=[TimeInterval.from_dict(r) for r in d.arr(m.get("reminders"), "reminders")],
            recurring_schedule=TimeInterval.from_optional(m.get("recurring_schedule")),
            comment=d.opt_string(m.get("comment")),
            attachments=[
                AttachmentFile.from_dict(a) for a in d.arr(m.get("attachments"), "attachments")
            ],
            created_at=d.string(m.get("created_at")),
            updated_at=d.string(m.get("updated_at")),
        )


@dataclass(frozen=True, slots=True)
class CreateTask:
    """Request body for creating a task.

    ``deadline`` and ``recurring_schedule`` are always sent (as null when unset);
    ``comment``, ``attachments`` (file UUIDs) and ``notify`` only when set.
    """

    title: str
    deadline: str | None = None
    assignees: list[str] = field(default_factory=list)
    references: list[TaskReferenceInput] = field(default_factory=list)
    reminders: list[TimeInterval] = field(default_factory=list)
    recurring_schedule: TimeInterval | None = None
    comment: str | None = None
    attachments: list[str] | None = None
    notify: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "title": self.title,
            "deadline": self.deadline,
            "assignees": list(self.assignees),
            "references": [r.to_dict() for r in self.references],
            "reminders": [r.to_dict() for r in self.reminders],
            "recurring_schedule": (
                self.recurring_schedule.to_dict() if self.recurring_schedule else None
            ),
        }
        if self.comment is not None:
            body["comment"] = self.comment
        if self.attachments:
            body["attachments"] = list(self.attachments)
        if self.notify is not None:
            body["notify"] = self.notify
        return body


@dataclass(frozen=True, slots=True)
class UpdateTask(CreateTask):
    """Request body for replacing a task (same shape as CreateTask)."""
