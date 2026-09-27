"""Asynchronous client.

This module is the source for the generated synchronous client in
``seventhings/_sync/client.py`` (see ``scripts/unasync.py``). Edit this file,
then regenerate.
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from types import TracebackType
from typing import IO, Any, TypeVar

import httpx

from .. import _operations as ops
from .._pagination import DEFAULT_PAGE_SIZE, options_for_page
from .._transport import (
    JSON,
    UNSET,
    Operation,
    Response,
    build_request,
    default_headers,
    to_response,
)
from .._transport import base_url as api_base_url
from ..errors import NetworkError
from ..models.auth import PingResponse, TokenResponse
from ..models.circularity_hub import AddObjectEntry, CircularityHubOrder, FilterObject
from ..models.enums import AssetTrackingTemplate, SSOAppTarget, SSOProviderName, TaskStatus
from ..models.field_definitions import (
    SYSTEM_MANAGED_FIELD_KEYS,
    CreateFieldDefinition,
    FieldDefinition,
    UpdateFieldDefinition,
)
from ..models.fields import Fields
from ..models.files import File, FileAttachment
from ..models.history import (
    HistoryResponse,
    LocationHistoryEntry,
    ObjectHistoryEntry,
    PersonHistoryEntry,
    RentalCaseHistoryEntry,
    RoomHistoryEntry,
    TaskHistoryEntry,
)
from ..models.list_options import (
    HistoryListOptions,
    ListOptions,
    PersonListOptions,
    TaskListOptions,
    UserListOptions,
)
from ..models.persons import Person, PersonListResponse
from ..models.rentals import CreateRentalCase, RentalCase, UpdateRentalCase
from ..models.reports import CreateReport, ReportTemplate
from ..models.tasks import CreateTask, Task, UpdateTask
from ..models.users import User, UserListResponse

T = TypeVar("T")

DEFAULT_TIMEOUT = 30.0


async def _walk(
    fetch: Callable[[int], Awaitable[builtins.list[T]]], per_page: int
) -> AsyncIterator[T]:
    """Yield items page by page, stopping after the first short (or empty) page."""
    page = 1
    while True:
        items = await fetch(page)
        for item in items:
            yield item
        if len(items) < per_page:
            return
        page += 1


class AsyncClient:
    """Asynchronous client for the seventhings Customer API.

    ``base_url`` is the instance URL, e.g. ``https://example.seventhings.com``.
    Pass ``http_client`` to use your own ``httpx.AsyncClient`` (it is not closed
    by this client); otherwise one is created with the given ``timeout``.
    """

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        client_id: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float | httpx.Timeout | None = DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = api_base_url(base_url)
        self.token = token
        self.client_id = client_id
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout, headers=default_headers())

        self.auth = AsyncAuthService(self)
        self.objects = AsyncObjectsService(self)
        self.rooms = AsyncRoomsService(self)
        self.locations = AsyncLocationsService(self)
        self.users = AsyncUsersService(self)
        self.persons = AsyncPersonsService(self)
        self.files = AsyncFilesService(self)
        self.tasks = AsyncTasksService(self)
        self.rentals = AsyncRentalsService(self)
        self.field_definitions = AsyncFieldDefinitionsService(self)
        self.circularity_hub = AsyncCircularityHubService(self)
        self.reports = AsyncReportsService(self)

    @classmethod
    async def with_credentials(
        cls,
        base_url: str,
        username: str,
        password: str,
        client_id: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float | httpx.Timeout | None = DEFAULT_TIMEOUT,
    ) -> AsyncClient:
        """Create a client and log in with username/password."""
        client = cls(base_url, http_client=http_client, timeout=timeout)
        try:
            await client.auth.login(username, password, client_id)
        except BaseException:
            await client.aclose()
            raise
        return client

    @property
    def base_url(self) -> str:
        """API base URL (instance URL + ``/customer-api/v1``)."""
        return self._base_url

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _send(self, op: Operation[T]) -> T:
        request = build_request(self._http, self._base_url, self.token, op)
        try:
            resp = await self._http.send(request)
        except httpx.TransportError as exc:
            raise NetworkError(str(exc) or type(exc).__name__) from exc
        return op.parse(to_response(resp))

    async def request(
        self,
        method: str,
        path: str,
        *,
        query: str = "",
        json: Any = UNSET,
        accept: str | None = JSON,
        authenticated: bool = True,
    ) -> Response:
        """Low-level escape hatch: perform a request relative to the API base URL.

        Raises APIError for status >= 400.
        """
        return await self._send(
            ops.raw(
                method, path, query=query, json=json, accept=accept, authenticated=authenticated
            )
        )

    async def ping(self) -> PingResponse:
        """Call the unauthenticated root endpoint."""
        return await self._send(ops.ping())


class _AsyncService:
    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def _send(self, op: Operation[T]) -> T:
        return await self._client._send(op)


class AsyncAuthService(_AsyncService):
    """Token endpoints. Successful logins store the access token on the client."""

    async def _store(self, op: Operation[TokenResponse]) -> TokenResponse:
        token = await self._send(op)
        self._client.token = token.access_token
        return token

    async def login(self, username: str, password: str, client_id: str) -> TokenResponse:
        self._client.client_id = client_id
        return await self._store(ops.login(username, password, client_id))

    async def login_sso(
        self,
        provider: SSOProviderName | str,
        auth_code: str,
        client_id: str,
        app_target: SSOAppTarget | str | None = None,
    ) -> TokenResponse:
        self._client.client_id = client_id
        return await self._store(ops.login_sso(provider, auth_code, client_id, app_target))

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """Exchange a refresh token, using the client ID from the last login."""
        return await self._store(ops.refresh(refresh_token, self._client.client_id or ""))

    async def revoke_tokens(self) -> None:
        """Revoke the current tokens server-side (the local token is kept)."""
        await self._send(ops.revoke_tokens())


class AsyncObjectsService(_AsyncService):
    """Objects (assets). Records are schema-free field maps."""

    async def list(self, opts: ListOptions | None = None) -> builtins.list[dict[str, Any]]:
        return await self._send(ops.resource_list("objects", opts, unwrap=False))

    async def all(self, opts: ListOptions | None = None) -> AsyncIterator[Fields]:
        """Iterate every object across all pages (``opts.page`` is ignored)."""

        async def fetch(page: int) -> builtins.list[dict[str, Any]]:
            return await self.list(options_for_page(opts, ListOptions, page))

        async for item in _walk(fetch, _per_page(opts)):
            yield Fields(item)

    async def count(self, opts: ListOptions | None = None) -> int:
        return await self._send(ops.resource_count("objects", opts))

    async def create(self, fields: Mapping[str, Any]) -> str:
        """Create an object and return its UUID."""
        return await self._send(ops.resource_create("object", fields))

    async def get(self, uuid: str) -> dict[str, Any]:
        return await self._send(ops.resource_get("object", uuid, unwrap=False))

    async def get_by_barcode(self, barcode: str) -> dict[str, Any]:
        """Look up an object by barcode (archived objects included)."""
        return await self._send(ops.object_get_by_barcode(barcode))

    async def patch(self, uuid: str, fields: Mapping[str, Any]) -> None:
        await self._send(ops.resource_patch("object", uuid, fields))

    async def delete(self, uuid: str) -> None:
        await self._send(ops.resource_delete("object", uuid))

    async def archive(self, uuid: str) -> None:
        await self._send(ops.object_archive(uuid, archive=True))

    async def unarchive(self, uuid: str) -> None:
        await self._send(ops.object_archive(uuid, archive=False))

    async def add_files(self, uuid: str, attachments: builtins.list[FileAttachment]) -> Response:
        """Attach uploaded files; the raw response may be 200 or 207 (multi-status)."""
        return await self._send(ops.object_files(uuid, attachments, add=True))

    async def remove_files(self, uuid: str, attachments: builtins.list[FileAttachment]) -> Response:
        return await self._send(ops.object_files(uuid, attachments, add=False))

    async def history(
        self, uuid: str, opts: HistoryListOptions | None = None
    ) -> HistoryResponse[ObjectHistoryEntry]:
        return await self._send(ops.object_history(uuid, opts))


class _AsyncSpaceService(_AsyncService):
    """Rooms and locations share one shape; ``{uuid, fields}`` envelopes are flattened."""

    _plural: str
    _singular: str

    async def list(self, opts: ListOptions | None = None) -> builtins.list[dict[str, Any]]:
        return await self._send(ops.resource_list(self._plural, opts, unwrap=True))

    async def all(self, opts: ListOptions | None = None) -> AsyncIterator[Fields]:
        """Iterate every record across all pages (``opts.page`` is ignored)."""

        async def fetch(page: int) -> builtins.list[dict[str, Any]]:
            return await self.list(options_for_page(opts, ListOptions, page))

        async for item in _walk(fetch, _per_page(opts)):
            yield Fields(item)

    async def count(self, opts: ListOptions | None = None) -> int:
        return await self._send(ops.resource_count(self._plural, opts))

    async def create(self, fields: Mapping[str, Any]) -> str:
        """Create a record and return its UUID."""
        return await self._send(ops.resource_create(self._singular, fields))

    async def get(self, uuid: str) -> dict[str, Any]:
        return await self._send(ops.resource_get(self._singular, uuid, unwrap=True))

    async def patch(self, uuid: str, fields: Mapping[str, Any]) -> dict[str, Any] | None:
        """Update fields; returns the updated record, or None if the API sent no body."""
        return await self._send(ops.resource_patch_unwrapped(self._singular, uuid, fields))

    async def delete(self, uuid: str) -> None:
        await self._send(ops.resource_delete(self._singular, uuid))


class AsyncRoomsService(_AsyncSpaceService):
    _plural = "rooms"
    _singular = "room"

    async def history(
        self, uuid: str, opts: HistoryListOptions | None = None
    ) -> HistoryResponse[RoomHistoryEntry]:
        return await self._send(ops.room_history(uuid, opts))


class AsyncLocationsService(_AsyncSpaceService):
    _plural = "locations"
    _singular = "location"

    async def history(
        self, uuid: str, opts: HistoryListOptions | None = None
    ) -> HistoryResponse[LocationHistoryEntry]:
        return await self._send(ops.location_history(uuid, opts))


class AsyncUsersService(_AsyncService):
    async def list(self, opts: UserListOptions | None = None) -> UserListResponse:
        return await self._send(ops.users_list(opts))

    async def all(self, opts: UserListOptions | None = None) -> AsyncIterator[User]:
        """Iterate every user across all pages (``opts.page`` is ignored)."""

        async def fetch(page: int) -> builtins.list[User]:
            return (await self.list(options_for_page(opts, UserListOptions, page))).items

        async for user in _walk(fetch, _per_page(opts)):
            yield user

    async def get(self, uuid: str) -> User:
        return await self._send(ops.user_get(uuid))

    async def get_by_id(self, user_id: int) -> User:
        return await self._send(ops.user_get_by_id(user_id))


class AsyncPersonsService(_AsyncService):
    async def list(self, opts: PersonListOptions | None = None) -> PersonListResponse:
        return await self._send(ops.persons_list(opts))

    async def all(self, opts: PersonListOptions | None = None) -> AsyncIterator[Person]:
        """Iterate every person across all pages (``opts.page`` is ignored)."""

        async def fetch(page: int) -> builtins.list[Person]:
            return (await self.list(options_for_page(opts, PersonListOptions, page))).items

        async for person in _walk(fetch, _per_page(opts)):
            yield person

    async def count(self, opts: PersonListOptions | None = None) -> int:
        return await self._send(ops.persons_count(opts))

    async def get(self, uuid: str) -> Person:
        return await self._send(ops.person_get(uuid))

    async def get_by_id(self, person_id: int) -> Person:
        return await self._send(ops.person_get_by_id(person_id))

    async def create(self, fields: Mapping[str, Any]) -> str:
        """Create a person and return its UUID."""
        return await self._send(ops.person_create(fields))

    async def patch(self, uuid: str, fields: Mapping[str, Any]) -> None:
        await self._send(ops.resource_patch("person", uuid, fields))

    async def delete(self, uuid: str) -> None:
        await self._send(ops.resource_delete("person", uuid))

    async def create_user(self, filter: FilterObject) -> None:
        """Create user accounts for the persons matching ``filter.filter`` (sort is ignored)."""
        await self._send(ops.person_create_user(filter))

    async def history(
        self, uuid: str, opts: HistoryListOptions | None = None
    ) -> HistoryResponse[PersonHistoryEntry]:
        return await self._send(ops.person_history(uuid, opts))


class AsyncFilesService(_AsyncService):
    async def list(self) -> builtins.list[File]:
        """The most recent files (the API returns at most 20; no paging)."""
        return await self._send(ops.files_list())

    async def get(self, uuid: str) -> File:
        return await self._send(ops.file_get(uuid))

    async def upload(self, filename: str, data: bytes | IO[bytes]) -> str:
        """Upload a file (multipart field ``data``) and return its UUID."""
        return await self._send(ops.file_upload(filename, data))

    async def get_data(self, uuid: str) -> bytes:
        return await self._send(ops.file_data(uuid, thumbnail=False))

    async def get_thumbnail(self, uuid: str) -> bytes:
        return await self._send(ops.file_data(uuid, thumbnail=True))


class AsyncTasksService(_AsyncService):
    async def list(self, opts: TaskListOptions | None = None) -> builtins.list[Task]:
        return await self._send(ops.tasks_list(opts))

    async def get(self, uuid: str) -> Task:
        return await self._send(ops.task_get(uuid))

    async def create(self, task: CreateTask) -> str:
        """Create a task and return its UUID."""
        return await self._send(ops.task_create(task))

    async def update(self, uuid: str, task: UpdateTask) -> None:
        """Replace a task (PUT)."""
        await self._send(ops.task_update(uuid, task))

    async def delete(self, uuid: str) -> None:
        await self._send(ops.task_delete(uuid))

    async def update_status(self, uuid: str, status: TaskStatus | str) -> None:
        await self._send(ops.task_update_status(uuid, status))

    async def history(
        self, uuid: str, opts: HistoryListOptions | None = None
    ) -> HistoryResponse[TaskHistoryEntry]:
        return await self._send(ops.task_history(uuid, opts))


class AsyncRentalsService(_AsyncService):
    async def list(self, opts: ListOptions | None = None) -> builtins.list[RentalCase]:
        return await self._send(ops.rentals_list(opts))

    async def all(self, opts: ListOptions | None = None) -> AsyncIterator[RentalCase]:
        """Iterate every rental case across all pages (``opts.page`` is ignored)."""

        async def fetch(page: int) -> builtins.list[RentalCase]:
            return await self.list(options_for_page(opts, ListOptions, page))

        async for rental in _walk(fetch, _per_page(opts)):
            yield rental

    async def get(self, uuid: str) -> RentalCase:
        return await self._send(ops.rental_get(uuid))

    async def create(self, rental: CreateRentalCase) -> str:
        """Create a rental case and return its UUID."""
        return await self._send(ops.rental_create(rental))

    async def update(self, uuid: str, rental: UpdateRentalCase) -> None:
        """Replace a rental case (PUT)."""
        await self._send(ops.rental_update(uuid, rental))

    async def delete(self, uuid: str) -> None:
        await self._send(ops.rental_delete(uuid))

    async def history(
        self, uuid: str, opts: HistoryListOptions | None = None
    ) -> HistoryResponse[RentalCaseHistoryEntry]:
        return await self._send(ops.rental_history(uuid, opts))


class AsyncFieldDefinitionsService(_AsyncService):
    async def list(self, template: AssetTrackingTemplate | str) -> builtins.list[FieldDefinition]:
        return await self._send(ops.field_definitions_list(template))

    async def get(self, template: AssetTrackingTemplate | str, uuid: str) -> FieldDefinition:
        return await self._send(ops.field_definition_get(template, uuid))

    async def create(
        self, template: AssetTrackingTemplate | str, definition: CreateFieldDefinition
    ) -> str:
        """Create a field definition and return its UUID."""
        return await self._send(ops.field_definition_create(template, definition))

    async def update(
        self,
        template: AssetTrackingTemplate | str,
        uuid: str,
        definition: UpdateFieldDefinition,
    ) -> None:
        await self._send(ops.field_definition_update(template, uuid, definition))

    async def mandatory(
        self, template: AssetTrackingTemplate | str
    ) -> builtins.list[FieldDefinition]:
        """Definitions callers must fill in (mandatory and not system-managed)."""
        return [
            d
            for d in await self.list(template)
            if d.is_mandatory() and d.field_key not in SYSTEM_MANAGED_FIELD_KEYS
        ]

    async def missing_mandatory_fields(
        self, template: AssetTrackingTemplate | str, fields: Mapping[str, Any]
    ) -> builtins.list[str]:
        """Keys of mandatory fields that are absent or null in ``fields``."""
        return [
            d.field_key for d in await self.mandatory(template) if fields.get(d.field_key) is None
        ]


class AsyncCircularityHubService(_AsyncService):
    """Circularity Hub. Items and orders use integer IDs, not UUIDs."""

    async def suggest_category(self, filter: FilterObject) -> dict[str, str] | None:
        """Category suggestions, or None when the API has none."""
        return await self._send(ops.hub_suggest_category(filter))

    async def suggest_rest_price(self, values: Mapping[str, str]) -> dict[str, str] | None:
        """Rest-price suggestions, or None when the API has none."""
        return await self._send(ops.hub_suggest_rest_price(values))

    async def add_objects(self, entries: Mapping[str, AddObjectEntry]) -> None:
        """Add objects (keyed by object UUID) to the hub."""
        await self._send(ops.hub_add_objects(entries))

    async def list_items(self, opts: ListOptions | None = None) -> builtins.list[dict[str, Any]]:
        return await self._send(ops.hub_items_list(opts))

    async def all_items(self, opts: ListOptions | None = None) -> AsyncIterator[Fields]:
        """Iterate every hub item across all pages (``opts.page`` is ignored)."""

        async def fetch(page: int) -> builtins.list[dict[str, Any]]:
            return await self.list_items(options_for_page(opts, ListOptions, page))

        async for item in _walk(fetch, _per_page(opts)):
            yield Fields(item)

    async def get_item(self, item_id: int) -> dict[str, Any]:
        return await self._send(ops.hub_item_get(item_id))

    async def update_item(self, item_id: int, fields: Mapping[str, Any]) -> None:
        await self._send(ops.hub_item_update(item_id, fields))

    async def delete_item(self, item_id: int) -> None:
        await self._send(ops.hub_item_delete(item_id))

    async def list_orders(
        self, opts: ListOptions | None = None
    ) -> builtins.list[CircularityHubOrder]:
        return await self._send(ops.hub_orders_list(opts))

    async def create_order(self, item_ids: builtins.list[int]) -> int:
        """Create an order for the given item IDs and return the order ID."""
        return await self._send(ops.hub_order_create(item_ids))

    async def get_order(self, order_id: int) -> CircularityHubOrder:
        return await self._send(ops.hub_order_get(order_id))

    async def update_order(self, order_id: int, fields: Mapping[str, Any]) -> None:
        await self._send(ops.hub_order_update(order_id, fields))


class AsyncReportsService(_AsyncService):
    async def list_templates(self) -> builtins.list[ReportTemplate]:
        return await self._send(ops.report_templates_list())

    async def create(self, report: CreateReport) -> bytes:
        """Render a report and return the PDF bytes."""
        return await self._send(ops.report_create(report))


def _per_page(opts: ListOptions | UserListOptions | PersonListOptions | None) -> int:
    return (opts.per_page if opts is not None else None) or DEFAULT_PAGE_SIZE
