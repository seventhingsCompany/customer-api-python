from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import _decode as d


@dataclass(frozen=True, slots=True)
class File:
    uuid: str
    name: str
    type: str
    size: int
    creator_id: int
    created_at: str
    data_uri: str
    thumbnail_uri: str

    @classmethod
    def from_dict(cls, data: Any) -> File:
        m = d.obj(data, "file")
        return cls(
            uuid=d.string(m.get("uuid")),
            name=d.string(m.get("name")),
            type=d.string(m.get("type")),
            size=d.integer(m.get("size")),
            creator_id=d.integer(m.get("creator_id")),
            created_at=d.string(m.get("created_at")),
            data_uri=d.string(m.get("data_uri")),
            thumbnail_uri=d.string(m.get("thumbnail_uri")),
        )


@dataclass(frozen=True, slots=True)
class AttachmentFile:
    """A file attached to a task or rental case."""

    uuid: str
    name: str
    type: str
    size: int
    data_uri: str
    thumbnail_uri: str

    @classmethod
    def from_dict(cls, data: Any) -> AttachmentFile:
        m = d.obj(data, "attachment")
        return cls(
            uuid=d.string(m.get("uuid")),
            name=d.string(m.get("name")),
            type=d.string(m.get("type")),
            size=d.integer(m.get("size")),
            data_uri=d.string(m.get("data_uri")),
            thumbnail_uri=d.string(m.get("thumbnail_uri")),
        )


@dataclass(frozen=True, slots=True)
class FileAttachment:
    """Links an uploaded file to an attachment field of an object."""

    field_key: str
    file_uuid: str

    def to_dict(self) -> dict[str, Any]:
        return {"field-key": self.field_key, "file-uuid": self.file_uuid}
