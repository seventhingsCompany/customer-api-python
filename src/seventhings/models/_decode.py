"""Lenient helpers for turning decoded JSON into model attributes.

Missing or null values fall back to the zero value, like Go's encoding/json.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, TypeVar

from ..errors import DecodeError

E = TypeVar("E", bound=Enum)


def obj(data: Any, what: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise DecodeError(f"expected a JSON object for {what}, got {type(data).__name__}")
    return data


def arr(data: Any, what: str) -> list[Any]:
    if data is None:
        return []
    if not isinstance(data, list):
        raise DecodeError(f"expected a JSON array for {what}, got {type(data).__name__}")
    return data


def string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def opt_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def integer(value: Any) -> int:
    result = opt_integer(value)
    return 0 if result is None else result


def opt_integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def opt_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def boolean(value: Any) -> bool:
    return value if isinstance(value, bool) else False


def enum(cls: type[E], value: Any) -> E | str:
    """Return the enum member for value, or the raw string for values unknown to this SDK."""
    try:
        return cls(value)
    except ValueError:
        return string(value)


def str_list(value: Any) -> list[str]:
    return [v for v in arr(value, "string list") if isinstance(v, str)]
