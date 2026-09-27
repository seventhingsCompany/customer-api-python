"""Exceptions raised by the seventhings client."""

from __future__ import annotations

import json

FEATURE_INACTIVE_MESSAGE = "The required feature for this endpoint is not active"


class SeventhingsError(Exception):
    """Base class for every exception raised by this SDK."""


class APIError(SeventhingsError):
    """The API answered with an HTTP status code >= 400."""

    def __init__(self, status_code: int, status: str, body: str) -> None:
        self.status_code = status_code
        self.status = status
        self.body = body
        super().__init__(f"seventhings API error {status_code} ({status}): {body}")

    def is_status_code(self, code: int) -> bool:
        return self.status_code == code

    @property
    def is_not_found(self) -> bool:
        return self.status_code == 404

    @property
    def is_unauthorized(self) -> bool:
        return self.status_code == 401

    @property
    def is_forbidden(self) -> bool:
        return self.status_code == 403

    @property
    def is_conflict(self) -> bool:
        return self.status_code == 409

    @property
    def is_rate_limited(self) -> bool:
        return self.status_code == 429

    @property
    def is_server_error(self) -> bool:
        return self.status_code >= 500

    @property
    def is_feature_inactive(self) -> bool:
        """True for a 403 caused by a module (e.g. rentals) not being active on the instance."""
        if self.status_code != 403:
            return False
        try:
            data = json.loads(self.body)
        except ValueError:
            return False
        return isinstance(data, dict) and data.get("message") == FEATURE_INACTIVE_MESSAGE


class NetworkError(SeventhingsError):
    """The request could not be completed (connection failure, timeout, ...)."""


class DecodeError(SeventhingsError, ValueError):
    """A response could not be decoded into the expected shape."""
