"""API-surface checks: Go SDK parity and sync/async parity."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from seventhings import AsyncClient, Client

# Every exported method of the Go client (customer-api-go/client) -> Python path.
GO_PARITY = {
    "Ping": "ping",
    "Login": "auth.login",
    "LoginSSO": "auth.login_sso",
    "Refresh": "auth.refresh",
    "RevokeTokens": "auth.revoke_tokens",
    "Token": "token",
    "SetToken": "token",
    "ClientID": "client_id",
    "Get": "request",
    "Post": "request",
    "Patch": "request",
    "Put": "request",
    "Delete": "request",
    "DoUnauthenticated": "request",
    "GetRaw": "request",
    "PostMultipart": "files.upload",
    "ObjectsList": "objects.list",
    "ObjectsAll": "objects.all",
    "ObjectsCount": "objects.count",
    "ObjectCreate": "objects.create",
    "ObjectGet": "objects.get",
    "ObjectGetByBarcode": "objects.get_by_barcode",
    "ObjectPatch": "objects.patch",
    "ObjectDelete": "objects.delete",
    "ObjectArchive": "objects.archive",
    "ObjectUnarchive": "objects.unarchive",
    "ObjectAddFiles": "objects.add_files",
    "ObjectRemoveFiles": "objects.remove_files",
    "ObjectHistory": "objects.history",
    "RoomsList": "rooms.list",
    "RoomsAll": "rooms.all",
    "RoomsCount": "rooms.count",
    "RoomCreate": "rooms.create",
    "RoomGet": "rooms.get",
    "RoomPatch": "rooms.patch",
    "RoomDelete": "rooms.delete",
    "RoomHistory": "rooms.history",
    "LocationsList": "locations.list",
    "LocationsAll": "locations.all",
    "LocationsCount": "locations.count",
    "LocationCreate": "locations.create",
    "LocationGet": "locations.get",
    "LocationPatch": "locations.patch",
    "LocationDelete": "locations.delete",
    "LocationHistory": "locations.history",
    "UsersList": "users.list",
    "UsersAll": "users.all",
    "UserGet": "users.get",
    "UserGetByID": "users.get_by_id",
    "PersonsList": "persons.list",
    "PersonsAll": "persons.all",
    "PersonsCount": "persons.count",
    "PersonGet": "persons.get",
    "PersonGetByID": "persons.get_by_id",
    "PersonCreate": "persons.create",
    "PersonPatch": "persons.patch",
    "PersonDelete": "persons.delete",
    "PersonCreateUser": "persons.create_user",
    "PersonHistory": "persons.history",
    "FilesList": "files.list",
    "FileGet": "files.get",
    "FileUpload": "files.upload",
    "FileGetData": "files.get_data",
    "FileGetThumbnail": "files.get_thumbnail",
    "TasksList": "tasks.list",
    "TaskCreate": "tasks.create",
    "TaskGet": "tasks.get",
    "TaskUpdate": "tasks.update",
    "TaskDelete": "tasks.delete",
    "TaskUpdateStatus": "tasks.update_status",
    "TaskHistory": "tasks.history",
    "RentalCasesList": "rentals.list",
    "RentalCasesAll": "rentals.all",
    "RentalCaseCreate": "rentals.create",
    "RentalCaseGet": "rentals.get",
    "RentalCaseUpdate": "rentals.update",
    "RentalCaseDelete": "rentals.delete",
    "RentalCaseHistory": "rentals.history",
    "FieldDefinitionsList": "field_definitions.list",
    "FieldDefinitionGet": "field_definitions.get",
    "FieldDefinitionCreate": "field_definitions.create",
    "FieldDefinitionUpdate": "field_definitions.update",
    "MandatoryFieldDefinitions": "field_definitions.mandatory",
    "MissingMandatoryFields": "field_definitions.missing_mandatory_fields",
    "CircularityHubSuggestCategory": "circularity_hub.suggest_category",
    "CircularityHubSuggestRestPrice": "circularity_hub.suggest_rest_price",
    "CircularityHubAddObjects": "circularity_hub.add_objects",
    "CircularityHubItemsList": "circularity_hub.list_items",
    "CircularityHubItemsAll": "circularity_hub.all_items",
    "CircularityHubItemGet": "circularity_hub.get_item",
    "CircularityHubItemUpdate": "circularity_hub.update_item",
    "CircularityHubItemDelete": "circularity_hub.delete_item",
    "CircularityHubOrdersList": "circularity_hub.list_orders",
    "CircularityHubOrderCreate": "circularity_hub.create_order",
    "CircularityHubOrderGet": "circularity_hub.get_order",
    "CircularityHubOrderUpdate": "circularity_hub.update_order",
    "ReportTemplatesList": "reports.list_templates",
    "ReportCreate": "reports.create",
}


def _resolve(obj: Any, path: str) -> Any:
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


@pytest.mark.parametrize("client_cls", [Client, AsyncClient])
@pytest.mark.parametrize(("go_name", "py_path"), sorted(GO_PARITY.items()))
def test_go_method_has_python_counterpart(client_cls: Any, go_name: str, py_path: str) -> None:
    client = client_cls("https://x.example", token="t")
    _resolve(client, py_path)


def _public_methods(obj: Any) -> dict[str, inspect.Signature]:
    return {
        name: inspect.signature(member)
        for name, member in inspect.getmembers(obj, callable)
        if not name.startswith("_")
    }


SERVICES = [
    "auth",
    "objects",
    "rooms",
    "locations",
    "users",
    "persons",
    "files",
    "tasks",
    "rentals",
    "field_definitions",
    "circularity_hub",
    "reports",
]


@pytest.mark.parametrize("service", SERVICES)
def test_sync_and_async_services_match(service: str) -> None:
    sync = _public_methods(getattr(Client("https://x"), service))
    asy = _public_methods(getattr(AsyncClient("https://x"), service))
    assert sync.keys() == asy.keys()
    for name in sync:
        assert list(sync[name].parameters) == list(asy[name].parameters), name


def test_sync_and_async_clients_match() -> None:
    sync = set(_public_methods(Client("https://x"))) - {"close"}
    asy = set(_public_methods(AsyncClient("https://x"))) - {"aclose"}
    assert sync == asy
