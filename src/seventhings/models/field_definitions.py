from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import _decode as d
from .enums import FieldTypeName

FIELD_ATTRIBUTE_MANDATORY = "mandatory"
CONSTRAINT_ALLOWED_VALUES = "allowed_values"
_MANDATORY_VALUE = "yes"

SYSTEM_MANAGED_FIELD_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "uuid",
        "person_uuid",
        "user_uuid",
        "asset_uuid",
        "room_uuid",
        "location_uuid",
        "created_at",
        "updated_at",
        "updated_by_user_id",
        "imported_by_user_id",
        "imported_with_template_id",
        "imported_at",
        "created_on_import_with_template_id",
    }
)
"""Field keys the server fills in itself; never required from callers."""


@dataclass(frozen=True, slots=True)
class FieldValueConstraint:
    type: str
    value: Any

    @classmethod
    def from_dict(cls, data: Any) -> FieldValueConstraint:
        m = d.obj(data, "field constraint")
        return cls(type=d.string(m.get("type")), value=m.get("value"))

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "value": self.value}


@dataclass(frozen=True, slots=True)
class FieldAttribute:
    type: str
    value: Any

    @classmethod
    def from_dict(cls, data: Any) -> FieldAttribute:
        m = d.obj(data, "field attribute")
        return cls(type=d.string(m.get("type")), value=m.get("value"))

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "value": self.value}


@dataclass(frozen=True, slots=True)
class FieldRelation:
    type: str
    field_uuid: str
    comparison_values: list[Any] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Any) -> FieldRelation:
        m = d.obj(data, "field relation")
        return cls(
            type=d.string(m.get("type")),
            field_uuid=d.string(m.get("field_uuid")),
            comparison_values=d.arr(m.get("comparison_values"), "comparison values"),
        )

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"type": self.type, "field_uuid": self.field_uuid}
        if self.comparison_values:
            body["comparison_values"] = list(self.comparison_values)
        return body


@dataclass(frozen=True, slots=True)
class FieldDefinitionFieldType:
    name: FieldTypeName | str
    constraints: list[FieldValueConstraint] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Any) -> FieldDefinitionFieldType:
        m = d.obj(data, "field type")
        return cls(
            name=d.enum(FieldTypeName, m.get("name")),
            constraints=[
                FieldValueConstraint.from_dict(c)
                for c in d.arr(m.get("constraints"), "constraints")
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {"name": str(self.name), "constraints": [c.to_dict() for c in self.constraints]}

    def allowed_values(self) -> list[Any] | None:
        """Values of the ``allowed_values`` constraint (e.g. dropdown options), or None."""
        for c in self.constraints:
            if c.type == CONSTRAINT_ALLOWED_VALUES and isinstance(c.value, list):
                return c.value
        return None


@dataclass(frozen=True, slots=True)
class FieldDefinition:
    uuid: str
    field_key: str
    field_type: FieldDefinitionFieldType
    label: str
    attributes: list[FieldAttribute]
    relations: list[FieldRelation]
    comment: str | None
    default_value: Any
    possible_values: list[Any]

    @classmethod
    def from_dict(cls, data: Any) -> FieldDefinition:
        m = d.obj(data, "field definition")
        return cls(
            uuid=d.string(m.get("uuid")),
            field_key=d.string(m.get("field_key")),
            field_type=FieldDefinitionFieldType.from_dict(m.get("field_type") or {}),
            label=d.string(m.get("label")),
            attributes=[
                FieldAttribute.from_dict(a) for a in d.arr(m.get("attributes"), "attributes")
            ],
            relations=[FieldRelation.from_dict(r) for r in d.arr(m.get("relations"), "relations")],
            comment=d.opt_string(m.get("comment")),
            default_value=m.get("default_value"),
            possible_values=d.arr(m.get("possible_values"), "possible values"),
        )

    def has_attribute(self, attr_type: str) -> bool:
        return any(a.type == attr_type for a in self.attributes)

    def attribute(self, attr_type: str) -> Any:
        """Value of the first attribute of the given type, or None."""
        for a in self.attributes:
            if a.type == attr_type:
                return a.value
        return None

    def is_mandatory(self) -> bool:
        """True when the ``mandatory`` attribute is ``"yes"``."""
        return bool(self.attribute(FIELD_ATTRIBUTE_MANDATORY) == _MANDATORY_VALUE)


@dataclass(frozen=True, slots=True)
class CreateFieldDefinition:
    field_type: FieldDefinitionFieldType
    label: str
    attributes: list[FieldAttribute] = field(default_factory=list)
    relations: list[FieldRelation] = field(default_factory=list)
    comment: str | None = None
    default_value: Any = None
    possible_values: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_type": self.field_type.to_dict(),
            "label": self.label,
            "attributes": [a.to_dict() for a in self.attributes],
            "relations": [r.to_dict() for r in self.relations],
            "comment": self.comment,
            "default_value": self.default_value,
            "possible_values": list(self.possible_values),
        }


@dataclass(frozen=True, slots=True)
class UpdateFieldDefinition:
    uuid: str
    field_key: str
    field_type: FieldDefinitionFieldType
    label: str
    attributes: list[FieldAttribute] = field(default_factory=list)
    relations: list[FieldRelation] = field(default_factory=list)
    comment: str | None = None
    default_value: Any = None
    possible_values: list[Any] = field(default_factory=list)

    @classmethod
    def from_definition(cls, definition: FieldDefinition) -> UpdateFieldDefinition:
        """Start an update from an existing definition (change fields with dataclasses.replace)."""
        return cls(
            uuid=definition.uuid,
            field_key=definition.field_key,
            field_type=definition.field_type,
            label=definition.label,
            attributes=list(definition.attributes),
            relations=list(definition.relations),
            comment=definition.comment,
            default_value=definition.default_value,
            possible_values=list(definition.possible_values),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uuid": self.uuid,
            "field_key": self.field_key,
            "field_type": self.field_type.to_dict(),
            "label": self.label,
            "attributes": [a.to_dict() for a in self.attributes],
            "relations": [r.to_dict() for r in self.relations],
            "comment": self.comment,
            "default_value": self.default_value,
            "possible_values": list(self.possible_values),
        }
