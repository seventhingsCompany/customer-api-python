"""Python client for the seventhings Customer API.

from seventhings import Client

with Client.with_credentials(url, username, password, client_id) as client:
    for obj in client.objects.all():
        print(obj.uuid, obj.name)
"""

from ._async.client import AsyncClient
from ._rate_limit import DEFAULT_REQUESTS_PER_MINUTE
from ._sync.client import Client
from ._transport import Response
from ._version import __version__
from .errors import (
    APIError,
    DecodeError,
    NetworkError,
    RentalCaseRenterRequiredError,
    SeventhingsError,
)

__all__ = [
    "DEFAULT_REQUESTS_PER_MINUTE",
    "APIError",
    "AsyncClient",
    "Client",
    "DecodeError",
    "NetworkError",
    "RentalCaseRenterRequiredError",
    "Response",
    "SeventhingsError",
    "__version__",
]
