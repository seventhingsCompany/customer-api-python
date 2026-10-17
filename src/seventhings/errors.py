"""Exceptions raised by the seventhings client."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

FEATURE_INACTIVE_MESSAGE = "The required feature for this endpoint is not active"


class SeventhingsError(Exception):
    """Base class for every exception raised by this SDK."""


class APIError(SeventhingsError):
    """The API answered with an HTTP status code >= 400.

    ``headers`` is a copy of the response headers (including ``Retry-After``
    when sent); they are not part of the exception message.
    """

    def __init__(
        self, status_code: int, status: str, body: str, headers: httpx.Headers | None = None
    ) -> None:
        self.status_code = status_code
        self.status = status
        self.body = body
        self.headers = headers if headers is not None else httpx.Headers()
        super().__init__(f"seventhings API error {status_code} ({status}): {body}")

    def retry_after(self, now: datetime | None = None) -> timedelta | None:
        """Parse the ``Retry-After`` header as delay-seconds or an HTTP date.

        Dates are taken relative to ``now`` (default: the current UTC time); past
        dates give a zero delay. Missing, repeated or invalid values give None.
        This helper does not wait or retry; the caller decides whether to requeue.
        """
        values = self.headers.get_list("Retry-After")
        if len(values) != 1:
            return None
        value = values[0].strip()
        if not value:
            return None
        if value.isascii() and value.isdigit():
            try:
                return timedelta(seconds=int(value))
            except OverflowError:
                return None
        try:
            date = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        if now is None:
            now = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return max(date - now, timedelta(0))

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


class RentalCaseRenterRequiredError(SeventhingsError, ValueError):
    """A rental case create/update has no renter; raised before any request is sent.

    The API description marks the renter optional, but the server rejects null
    and fails with HTTP 500 when it is omitted.
    """

    def __init__(self) -> None:
        super().__init__(
            "rental case renter is required: provide a renter with type and value; "
            "the current API fails when renter is omitted"
        )


class NetworkError(SeventhingsError):
    """The request could not be completed (connection failure, timeout, ...)."""


class DecodeError(SeventhingsError, ValueError):
    """A response could not be decoded into the expected shape."""
