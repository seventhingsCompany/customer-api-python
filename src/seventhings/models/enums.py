"""String enums used by the API.

All enums subclass ``str`` so members compare equal to their wire values.
Response decoding is lenient: a value unknown to this SDK version is kept as a
plain ``str`` instead of raising.
"""

from __future__ import annotations

from enum import Enum


class _StrEnum(str, Enum):
    def __str__(self) -> str:
        return str(self.value)


class SSOProviderName(_StrEnum):
    AZURE = "azure-open-id-connect"
    GOOGLE = "google-open-id-connect"
    ONE_LOGIN = "one-login-open-id-connect"


class SSOAppTarget(_StrEnum):
    WEB = "web"
    MOBILE = "mobile"


class LoginDeniedReason(_StrEnum):
    """Value of ``detail`` in the body of a 403 login response."""

    LOGIN_DEACTIVATED = "LoginDeactivated"
    BANNED = "Banned"
    EMAIL_UNCONFIRMED = "EmailUnconfirmed"
    INACTIVE = "Inactive"
    ONLY_SSO_LOGIN_ALLOWED = "OnlySSOLoginAllowed"


class SortDirection(_StrEnum):
    ASC = "ASC"
    DESC = "DESC"


class FilterOperator(_StrEnum):
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GT_OR_NULL = "gt_or_null"
    GTE = "gte"
    GTE_OR_NULL = "gte_or_null"
    LT = "lt"
    LT_OR_NULL = "lt_or_null"
    LTE = "lte"
    LTE_OR_NULL = "lte_or_null"
    LIKE = "like"
    NOT_LIKE = "not_like"
    IN = "in"
    NIN = "nin"


class AssetTrackingTemplate(_StrEnum):
    ASSET = "asset"
    ROOM = "room"
    PERSON = "person"


class FieldTypeName(_StrEnum):
    ATTACHMENT = "ATTACHMENT"
    BARCODE = "BARCODE"
    BOOLEAN = "BOOLEAN"
    COORDINATES = "COORDINATES"
    DATE = "DATE"
    DATETIME = "DATETIME"
    DECIMAL = "DECIMAL"
    DROPDOWN = "DROPDOWN"
    FIELD_VALUE_COMPARISON = "FIELD_VALUE_COMPARISON"
    LINK = "LINK"
    LINKED_ASSETS = "LINKED_ASSETS"
    LINKED_LOCATION = "LINKED_LOCATION"
    LINKED_PERSON = "LINKED_PERSON"
    LINKED_ROOM = "LINKED_ROOM"
    LINKED_USER = "LINKED_USER"
    LONG_TEXT = "LONG_TEXT"
    MONEY = "MONEY"
    NUMBER = "NUMBER"
    REMINDER = "REMINDER"
    TEXT = "TEXT"


class RentalCaseStatus(_StrEnum):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    BORROWED = "borrowed"
    REJECTED = "rejected"
    COMPLETED = "completed"
    RETURN_OVERDUE = "return_overdue"
    PICKUP_OVERDUE = "pickup_overdue"


class RentalCaseReferenceType(_StrEnum):
    ASSET = "asset"


class RenterType(_StrEnum):
    PLAIN = "plain"
    USER = "user"


class TaskStatus(_StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class TaskReferenceType(_StrEnum):
    ASSET = "asset"


class TaskReferenceStatus(_StrEnum):
    OPEN = "open"
    DONE = "done"


class TimeIntervalUnit(_StrEnum):
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"


class UserSortBy(_StrEnum):
    ID = "id"
    EMAIL = "email"


class UserSortOrder(_StrEnum):
    """Sort order for users and persons (lowercase on the wire)."""

    ASC = "asc"
    DESC = "desc"
