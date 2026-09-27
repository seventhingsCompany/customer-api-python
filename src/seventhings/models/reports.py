from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import _decode as d


@dataclass(frozen=True, slots=True)
class ReportTemplate:
    uuid: str
    name: str

    @classmethod
    def from_dict(cls, data: Any) -> ReportTemplate:
        m = d.obj(data, "report template")
        return cls(uuid=d.string(m.get("uuid")), name=d.string(m.get("name")))


@dataclass(frozen=True, slots=True)
class CreateReport:
    report_template_uuid: str
    object_uuids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_template_uuid": self.report_template_uuid,
            "object_uuids": list(self.object_uuids),
        }
