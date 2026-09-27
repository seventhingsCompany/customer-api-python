from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import _decode as d


@dataclass(frozen=True, slots=True)
class TokenResponse:
    access_token: str
    expires_in: int
    token_type: str
    scope: str | None
    refresh_token: str
    user_id: int

    @classmethod
    def from_dict(cls, data: Any) -> TokenResponse:
        m = d.obj(data, "token response")
        return cls(
            access_token=d.string(m.get("access_token")),
            expires_in=d.integer(m.get("expires_in")),
            token_type=d.string(m.get("token_type")),
            scope=d.opt_string(m.get("scope")),
            refresh_token=d.string(m.get("refresh_token")),
            user_id=d.integer(m.get("user_id")),
        )


@dataclass(frozen=True, slots=True)
class PingResponse:
    status: str
    description: str

    @classmethod
    def from_dict(cls, data: Any) -> PingResponse:
        m = d.obj(data, "ping response")
        return cls(status=d.string(m.get("status")), description=d.string(m.get("description")))
