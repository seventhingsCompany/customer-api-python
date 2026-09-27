"""Typed access to schema-free records (objects, rooms, locations, hub items)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_TIME_FORMATS = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S")


class Fields(dict[str, Any]):
    """A ``dict`` of field key -> value with typed, non-raising accessors.

    Each ``get_*`` accessor returns None when the key is missing or the value
    has a different type.
    """

    def has(self, key: str) -> bool:
        """True when key is present and not null."""
        return self.get(key) is not None

    def get_str(self, key: str) -> str | None:
        v = self.get(key)
        return v if isinstance(v, str) else None

    def get_int(self, key: str) -> int | None:
        """Integer value; integral floats (e.g. ``3.0``) are accepted."""
        v = self.get(key)
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return None

    def get_float(self, key: str) -> float | None:
        v = self.get(key)
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        return None

    def get_bool(self, key: str) -> bool | None:
        v = self.get(key)
        return v if isinstance(v, bool) else None

    def get_time(self, key: str) -> datetime | None:
        """Parse ``Y-m-d``, ``Y-m-d H:i:s`` (both UTC) or an RFC 3339 timestamp."""
        v = self.get(key)
        if not isinstance(v, str) or not v:
            return None
        for fmt in _TIME_FORMATS:
            try:
                return datetime.strptime(v, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        if "T" not in v:
            return None
        try:
            parsed = datetime.fromisoformat(v[:-1] + "+00:00" if v.endswith("Z") else v)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else None

    @property
    def uuid(self) -> str:
        return self.get_str("uuid") or ""

    @property
    def name(self) -> str:
        return self.get_str("name") or ""
