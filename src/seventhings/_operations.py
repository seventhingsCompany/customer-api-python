"""One builder per endpoint: request description + response parser, no I/O.

The sync and async services both execute these, so request shapes and
decoding live in exactly one place.
"""

from __future__ import annotations

import posixpath
from collections.abc import Callable, Mapping
from typing import IO, Any, TypeVar

from ._transport import UNSET, Operation, Response, segment
from .errors import DecodeError
from .models import _decode as d
from .models.auth import PingResponse, TokenResponse
from .models.circularity_hub import AddObjectEntry, CircularityHubOrder, FilterObject
from .models.enums import AssetTrackingTemplate, SSOAppTarget, SSOProviderName, TaskStatus
from .models.field_definitions import (
    CreateFieldDefinition,
    FieldDefinition,
    UpdateFieldDefinition,
)
from .models.files import File, FileAttachment
from .models.history import (
    HistoryResponse,
    LocationHistoryEntry,
    ObjectHistoryEntry,
    PersonHistoryEntry,
    RentalCaseHistoryEntry,
    RoomHistoryEntry,
    TaskHistoryEntry,
)
from .models.list_options import (
    HistoryListOptions,
    ListOptions,
    PersonListOptions,
    TaskListOptions,
    UserListOptions,
)
from .models.persons import Person, PersonListResponse
from .models.rentals import CreateRentalCase, RentalCase, UpdateRentalCase
from .models.reports import CreateReport, ReportTemplate
from .models.tasks import CreateTask, Task, UpdateTask
from .models.users import User, UserListResponse

T = TypeVar("T")

AUTH_TOKEN_PATH = "auth_token"
PDF = "application/pdf"


# --- response helpers -------------------------------------------------------


def uuid_from_location(resp: Response) -> str:
    """Last path segment of the Location header (UUID of a newly created resource)."""
    loc = resp.header("Location")
    if not loc:
        raise DecodeError("missing Location header")
    uuid = posixpath.basename(loc.rstrip("/")) if loc.strip("/") else ""
    if uuid in ("", ".", "/"):
        raise DecodeError(f"empty path in Location header: {loc}")
    return uuid


def uuid_from_file_upload(resp: Response) -> str:
    return resp.header("Location-UUID") or uuid_from_location(resp)


def int_from_location_id(resp: Response) -> int:
    raw = resp.header("Location-Id")
    if not raw:
        raise DecodeError("missing Location-Id header")
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise DecodeError(f"invalid Location-Id header {raw!r}") from exc


def unwrap_resource_fields(resource: dict[str, Any]) -> dict[str, Any]:
    """Flatten a ``{uuid, fields}`` room/location envelope; flat maps pass through."""
    fields = resource.get("fields")
    uuid = resource.get("uuid")
    if not isinstance(fields, dict) or not isinstance(uuid, str):
        return resource
    fields.setdefault("uuid", uuid)
    return fields


def _none(_: Response) -> None:
    return None


def _raw(resp: Response) -> Response:
    return resp


def _bytes(resp: Response) -> bytes:
    return resp.content


def _map(resp: Response) -> dict[str, Any]:
    return d.obj(resp.json(), "response")


def _items(resp: Response) -> list[Any]:
    return d.arr(d.obj(resp.json(), "list response").get("items"), "items")


def _maps(resp: Response) -> list[dict[str, Any]]:
    return [d.obj(i, "item") for i in _items(resp)]


def _count(resp: Response) -> int:
    return d.integer(d.obj(resp.json(), "count response").get("count"))


def _unwrapped(resp: Response) -> dict[str, Any]:
    return unwrap_resource_fields(_map(resp))


def _unwrapped_or_none(resp: Response) -> dict[str, Any] | None:
    return _unwrapped(resp) if resp.content.strip() else None


def _unwrapped_list(resp: Response) -> list[dict[str, Any]]:
    return [unwrap_resource_fields(i) for i in _maps(resp)]


def _list_of(decode: Callable[[Any], T]) -> Callable[[Response], list[T]]:
    return lambda resp: [decode(i) for i in _items(resp)]


def _bare_list_of(decode: Callable[[Any], T]) -> Callable[[Response], list[T]]:
    return lambda resp: [decode(i) for i in d.arr(resp.json(), "list response")]


def _one(decode: Callable[[Any], T]) -> Callable[[Response], T]:
    return lambda resp: decode(resp.json())


def _string_map_or_none(resp: Response) -> dict[str, str] | None:
    # The suggest endpoints answer [] (not {}) when there is nothing to suggest.
    if resp.content.lstrip().startswith(b"["):
        return None
    return {k: str(v) for k, v in _map(resp).items()}


def _qs(opts: Any) -> str:
    return "" if opts is None else str(opts.encode())


# --- ping & auth ------------------------------------------------------------


def ping() -> Operation[PingResponse]:
    return Operation("GET", "", _one(PingResponse.from_dict), authenticated=False)


def _token(body: dict[str, Any]) -> Operation[TokenResponse]:
    return Operation(
        "POST", AUTH_TOKEN_PATH, _one(TokenResponse.from_dict), json=body, authenticated=False
    )


def login(username: str, password: str, client_id: str) -> Operation[TokenResponse]:
    return _token(
        {
            "grant_type": "password",
            "username": username,
            "password": password,
            "client_id": client_id,
        }
    )


def refresh(refresh_token: str, client_id: str) -> Operation[TokenResponse]:
    return _token(
        {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id}
    )


def login_sso(
    provider: SSOProviderName | str,
    auth_code: str,
    client_id: str,
    app_target: SSOAppTarget | str | None,
) -> Operation[TokenResponse]:
    body: dict[str, Any] = {
        "grant_type": "sso_auth_code",
        "provider_name": str(provider),
        "auth_code": auth_code,
        "client_id": client_id,
    }
    if app_target is not None:
        body["app_target"] = str(app_target)
    return _token(body)


def revoke_tokens() -> Operation[None]:
    return Operation("DELETE", AUTH_TOKEN_PATH, _none)


# --- generic field-map resources (objects, rooms, locations) ---------------


def resource_list(
    plural: str, opts: ListOptions | None, *, unwrap: bool
) -> Operation[list[dict[str, Any]]]:
    return Operation("GET", plural, _unwrapped_list if unwrap else _maps, query=_qs(opts))


def resource_count(plural: str, opts: ListOptions | None) -> Operation[int]:
    return Operation("GET", f"{plural}/count", _count, query=_qs(opts))


def resource_create(singular: str, fields: Mapping[str, Any]) -> Operation[str]:
    return Operation("POST", singular, uuid_from_location, json=dict(fields))


def resource_get(singular: str, uuid: str, *, unwrap: bool) -> Operation[dict[str, Any]]:
    return Operation("GET", f"{singular}/{segment(uuid)}", _unwrapped if unwrap else _map)


def resource_delete(singular: str, uuid: str) -> Operation[None]:
    return Operation("DELETE", f"{singular}/{segment(uuid)}", _none)


def resource_patch(singular: str, uuid: str, fields: Mapping[str, Any]) -> Operation[None]:
    return Operation("PATCH", f"{singular}/{segment(uuid)}", _none, json=dict(fields))


def resource_patch_unwrapped(
    singular: str, uuid: str, fields: Mapping[str, Any]
) -> Operation[dict[str, Any] | None]:
    return Operation("PATCH", f"{singular}/{segment(uuid)}", _unwrapped_or_none, json=dict(fields))


def _history(
    path: str, opts: HistoryListOptions | None, decode: Callable[[Any], T]
) -> Operation[HistoryResponse[T]]:
    return Operation(
        "GET",
        path,
        lambda resp: HistoryResponse.from_dict(resp.json(), decode),
        query=_qs(opts),
    )


# --- objects ----------------------------------------------------------------


def object_get_by_barcode(barcode: str) -> Operation[dict[str, Any]]:
    return Operation("GET", f"object/by-barcode/{segment(barcode)}", _map)


def object_archive(uuid: str, *, archive: bool) -> Operation[None]:
    action = "archive" if archive else "unarchive"
    return Operation("POST", f"object/{segment(uuid)}/{action}", _none)


def object_files(uuid: str, attachments: list[FileAttachment], *, add: bool) -> Operation[Response]:
    action = "add-file" if add else "remove-file"
    return Operation(
        "POST",
        f"object/{segment(uuid)}/{action}",
        _raw,
        json=[a.to_dict() for a in attachments],
    )


def object_history(
    uuid: str, opts: HistoryListOptions | None
) -> Operation[HistoryResponse[ObjectHistoryEntry]]:
    return _history(f"object/{segment(uuid)}/history", opts, lambda i: d.obj(i, "history entry"))


def room_history(
    uuid: str, opts: HistoryListOptions | None
) -> Operation[HistoryResponse[RoomHistoryEntry]]:
    return _history(f"room/{segment(uuid)}/history", opts, RoomHistoryEntry.from_dict)


def location_history(
    uuid: str, opts: HistoryListOptions | None
) -> Operation[HistoryResponse[LocationHistoryEntry]]:
    return _history(f"location/{segment(uuid)}/history", opts, LocationHistoryEntry.from_dict)


# --- users ------------------------------------------------------------------


def users_list(opts: UserListOptions | None) -> Operation[UserListResponse]:
    return Operation("GET", "users", _one(UserListResponse.from_dict), query=_qs(opts))


def user_get(uuid: str) -> Operation[User]:
    return Operation("GET", f"user/{segment(uuid)}", _one(User.from_dict))


def user_get_by_id(user_id: int) -> Operation[User]:
    return Operation("GET", f"user/by-id/{int(user_id)}", _one(User.from_dict))


# --- persons ----------------------------------------------------------------


def persons_list(opts: PersonListOptions | None) -> Operation[PersonListResponse]:
    return Operation("GET", "persons", _one(PersonListResponse.from_dict), query=_qs(opts))


def persons_count(opts: PersonListOptions | None) -> Operation[int]:
    return Operation("GET", "persons/count", _count, query=_qs(opts))


def person_get(uuid: str) -> Operation[Person]:
    return Operation("GET", f"person/{segment(uuid)}", _one(Person.from_dict))


def person_get_by_id(person_id: int) -> Operation[Person]:
    return Operation("GET", f"person/by-id/{int(person_id)}", _one(Person.from_dict))


def person_create(fields: Mapping[str, Any]) -> Operation[str]:
    # Unlike PATCH, create wraps the field map in {"fields": ...}.
    return Operation("POST", "person", uuid_from_location, json={"fields": dict(fields)})


def person_create_user(filter: FilterObject) -> Operation[None]:
    return Operation("POST", "persons/create-user", _none, json={"filter": filter.filter_dict()})


def person_history(
    uuid: str, opts: HistoryListOptions | None
) -> Operation[HistoryResponse[PersonHistoryEntry]]:
    return _history(f"person/{segment(uuid)}/history", opts, PersonHistoryEntry.from_dict)


# --- files ------------------------------------------------------------------


def files_list() -> Operation[list[File]]:
    return Operation("GET", "files", _list_of(File.from_dict))


def file_get(uuid: str) -> Operation[File]:
    return Operation("GET", f"file/{segment(uuid)}", _one(File.from_dict))


def file_upload(filename: str, data: bytes | IO[bytes]) -> Operation[str]:
    return Operation(
        "POST", "file", uuid_from_file_upload, files={"data": (filename, data)}, accept=None
    )


def file_data(uuid: str, *, thumbnail: bool) -> Operation[bytes]:
    kind = "thumbnail" if thumbnail else "data"
    return Operation("GET", f"file/{segment(uuid)}/{kind}", _bytes, accept=None)


# --- tasks ------------------------------------------------------------------

_TASKS = "task-management"


def tasks_list(opts: TaskListOptions | None) -> Operation[list[Task]]:
    return Operation("GET", f"{_TASKS}/tasks", _bare_list_of(Task.from_dict), query=_qs(opts))


def task_create(task: CreateTask) -> Operation[str]:
    return Operation("POST", f"{_TASKS}/task", uuid_from_location, json=task.to_dict())


def task_get(uuid: str) -> Operation[Task]:
    return Operation("GET", f"{_TASKS}/task/{segment(uuid)}", _one(Task.from_dict))


def task_update(uuid: str, task: UpdateTask) -> Operation[None]:
    return Operation("PUT", f"{_TASKS}/task/{segment(uuid)}", _none, json=task.to_dict())


def task_delete(uuid: str) -> Operation[None]:
    return Operation("DELETE", f"{_TASKS}/task/{segment(uuid)}", _none)


def task_update_status(uuid: str, status: TaskStatus | str) -> Operation[None]:
    return Operation(
        "PUT", f"{_TASKS}/task/{segment(uuid)}/status", _none, json={"status": str(status)}
    )


def task_history(
    uuid: str, opts: HistoryListOptions | None
) -> Operation[HistoryResponse[TaskHistoryEntry]]:
    return _history(f"{_TASKS}/task/{segment(uuid)}/history", opts, TaskHistoryEntry.from_dict)


# --- rental cases -----------------------------------------------------------

_RENTALS = "rental-management"


def rentals_list(opts: ListOptions | None) -> Operation[list[RentalCase]]:
    return Operation(
        "GET", f"{_RENTALS}/rental-cases", _list_of(RentalCase.from_dict), query=_qs(opts)
    )


def rental_create(rental: CreateRentalCase) -> Operation[str]:
    return Operation("POST", f"{_RENTALS}/rental-case", uuid_from_location, json=rental.to_dict())


def rental_get(uuid: str) -> Operation[RentalCase]:
    return Operation("GET", f"{_RENTALS}/rental-case/{segment(uuid)}", _one(RentalCase.from_dict))


def rental_update(uuid: str, rental: UpdateRentalCase) -> Operation[None]:
    return Operation("PUT", f"{_RENTALS}/rental-case/{segment(uuid)}", _none, json=rental.to_dict())


def rental_delete(uuid: str) -> Operation[None]:
    return Operation("DELETE", f"{_RENTALS}/rental-case/{segment(uuid)}", _none)


def rental_history(
    uuid: str, opts: HistoryListOptions | None
) -> Operation[HistoryResponse[RentalCaseHistoryEntry]]:
    return _history(
        f"{_RENTALS}/rental-case/{segment(uuid)}/history", opts, RentalCaseHistoryEntry.from_dict
    )


# --- field definitions ------------------------------------------------------


def _fd(template: AssetTrackingTemplate | str) -> str:
    return f"asset-tracking/{segment(str(template))}"


def field_definitions_list(
    template: AssetTrackingTemplate | str,
) -> Operation[list[FieldDefinition]]:
    return Operation(
        "GET", f"{_fd(template)}/field-definitions", _bare_list_of(FieldDefinition.from_dict)
    )


def field_definition_get(
    template: AssetTrackingTemplate | str, uuid: str
) -> Operation[FieldDefinition]:
    return Operation(
        "GET",
        f"{_fd(template)}/field-definition/{segment(uuid)}",
        _one(FieldDefinition.from_dict),
    )


def field_definition_create(
    template: AssetTrackingTemplate | str, definition: CreateFieldDefinition
) -> Operation[str]:
    return Operation(
        "POST",
        f"{_fd(template)}/field-definition",
        uuid_from_location,
        json=definition.to_dict(),
    )


def field_definition_update(
    template: AssetTrackingTemplate | str, uuid: str, definition: UpdateFieldDefinition
) -> Operation[None]:
    return Operation(
        "PUT",
        f"{_fd(template)}/field-definition/{segment(uuid)}",
        _none,
        json=definition.to_dict(),
    )


# --- circularity hub --------------------------------------------------------

_HUB = "circularity-hub"


def hub_suggest_category(filter: FilterObject) -> Operation[dict[str, str] | None]:
    return Operation("POST", f"{_HUB}/suggest-category", _string_map_or_none, json=filter.to_dict())


def hub_suggest_rest_price(values: Mapping[str, str]) -> Operation[dict[str, str] | None]:
    return Operation("POST", f"{_HUB}/suggest-rest-price", _string_map_or_none, json=dict(values))


def hub_add_objects(entries: Mapping[str, AddObjectEntry]) -> Operation[None]:
    return Operation(
        "POST",
        f"{_HUB}/add-objects-to-circularity-hub",
        _none,
        json={uuid: e.to_dict() for uuid, e in entries.items()},
    )


def hub_items_list(opts: ListOptions | None) -> Operation[list[dict[str, Any]]]:
    return Operation("GET", f"{_HUB}/items", _maps, query=_qs(opts))


def hub_item_get(item_id: int) -> Operation[dict[str, Any]]:
    return Operation("GET", f"{_HUB}/item/{int(item_id)}", _map)


def hub_item_update(item_id: int, fields: Mapping[str, Any]) -> Operation[None]:
    return Operation("PATCH", f"{_HUB}/item/{int(item_id)}", _none, json=dict(fields))


def hub_item_delete(item_id: int) -> Operation[None]:
    return Operation("DELETE", f"{_HUB}/item/{int(item_id)}", _none)


def hub_orders_list(opts: ListOptions | None) -> Operation[list[CircularityHubOrder]]:
    return Operation(
        "GET", f"{_HUB}/orders", _list_of(CircularityHubOrder.from_dict), query=_qs(opts)
    )


def hub_order_create(item_ids: list[int]) -> Operation[int]:
    return Operation(
        "POST", f"{_HUB}/orders", int_from_location_id, json=[int(i) for i in item_ids]
    )


def hub_order_get(order_id: int) -> Operation[CircularityHubOrder]:
    return Operation("GET", f"{_HUB}/order/{int(order_id)}", _one(CircularityHubOrder.from_dict))


def hub_order_update(order_id: int, fields: Mapping[str, Any]) -> Operation[None]:
    return Operation("PATCH", f"{_HUB}/order/{int(order_id)}", _none, json=dict(fields))


# --- reports ----------------------------------------------------------------


def report_templates_list() -> Operation[list[ReportTemplate]]:
    return Operation("GET", "report-template", _bare_list_of(ReportTemplate.from_dict))


def report_create(report: CreateReport) -> Operation[bytes]:
    return Operation("POST", "report", _bytes, json=report.to_dict(), accept=PDF)


# --- raw requests -------------------------------------------------------------


def raw(
    method: str,
    path: str,
    *,
    query: str = "",
    json: Any = UNSET,
    accept: str | None,
    authenticated: bool,
) -> Operation[Response]:
    return Operation(
        method.upper(),
        path,
        _raw,
        query=query,
        json=json,
        accept=accept,
        authenticated=authenticated,
    )
