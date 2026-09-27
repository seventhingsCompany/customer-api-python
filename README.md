# seventhings Python SDK

Python client for the seventhings Customer API (`/customer-api/v1`). It offers the same features as the [Go](https://github.com/SeventhingsCompany/customer-api-go) and [PHP](https://github.com/SeventhingsCompany/customer-api-php) SDKs (v1.4.0) and comes with both a synchronous and an asynchronous client.

- Python 3.10+
- The only runtime dependency is [`httpx`](https://www.python-httpx.org/)
- Fully typed (`py.typed`), with dataclass models

## Installation

```sh
pip install "git+ssh://git@github.com/SeventhingsCompany/customer-api-python.git@v1.4.0"
# or
uv add "seventhings-customer-api @ git+ssh://git@github.com/SeventhingsCompany/customer-api-python.git@v1.4.0"
```

## Quick Start

### Password authentication

```python
from seventhings import Client

with Client.with_credentials(
    "https://example.seventhings.com", "user@example.com", "password", "client-id"
) as client:
    print(client.objects.count())
```

### Pre-existing token

```python
client = Client("https://example.seventhings.com", token="my-jwt-token")
```

### Manual login and refresh

```python
client = Client("https://example.seventhings.com")
tok = client.auth.login("user@example.com", "password", "client-id")  # stores the access token
tok = client.auth.refresh(tok.refresh_token)  # reuses the client ID from login
client.auth.revoke_tokens()
```

### SSO authentication

```python
from seventhings.models import SSOAppTarget, SSOProviderName

tok = client.auth.login_sso(SSOProviderName.AZURE, auth_code, "client-id", SSOAppTarget.WEB)
```

### Async

`AsyncClient` has the same API as `Client`, except that its methods are coroutines, the `all()` iterators are async iterators, and you close it with `aclose()` or `async with`:

```python
from seventhings import AsyncClient

async with await AsyncClient.with_credentials(url, user, password, client_id) as client:
    obj = await client.objects.get(uuid)
    async for room in client.rooms.all():
        print(room.name)
```

### Configuration

```python
Client(
    base_url,  # instance URL; "/customer-api/v1" is appended
    token=None,  # bearer token
    client_id=None,  # OAuth client ID used by auth.refresh()
    http_client=None,  # your own httpx.Client / httpx.AsyncClient (not closed by the SDK)
    timeout=30.0,  # seconds; None disables the timeout
)
```

## Usage

### Ping

```python
ping = client.ping()  # unauthenticated
print(ping.status)  # "OK"
```

### Objects

Objects have a schema that differs per tenant, so they are plain `dict`s. The `all()` iterator yields `Fields`, a `dict` with typed accessors.

```python
from seventhings.models import ListOptions, SortDirection, like

uuid = client.objects.create({"inventory_name": "Laptop", "barcode": "INV-001"})
obj = client.objects.get(uuid)
obj = client.objects.get_by_barcode("INV-001")  # archived objects included
client.objects.patch(uuid, {"inventory_name": "Laptop (IT)"})
client.objects.archive(uuid)
client.objects.unarchive(uuid)
client.objects.delete(uuid)

page = client.objects.list(ListOptions(page=1, per_page=50).where(like("inventory_name", "Laptop")))
total = client.objects.count()

for obj in client.objects.all(ListOptions(per_page=100)):  # walks every page
    print(obj.uuid, obj.get_str("inventory_name"), obj.get_time("updated_at"))
```

To attach a file you have already uploaded to an attachment field, use `add_files`. It returns the raw `Response`, because the API can answer `207 Multi-Status`:

```python
from seventhings.models import FileAttachment

resp = client.objects.add_files(uuid, [FileAttachment("documents", file_uuid)])
client.objects.remove_files(uuid, [FileAttachment("documents", file_uuid)])
```

### History

Objects, rooms, locations, persons, tasks and rental cases all have a paged history. The API defaults to page 1 with 50 entries per page (maximum 200).

```python
from seventhings.models import HistoryListOptions

hist = client.persons.history(person_uuid, HistoryListOptions(page=1, per_page=20))
for entry in hist.items:
    print(entry.occurred_at, entry.event_name, entry.details)  # details is a JSON string
if hist.page * hist.per_page < hist.total:
    ...  # fetch the next page
```

Object history entries are plain `dict`s, because their shape depends on `type` (`asset`, `task`, `rental_case` or `object_merge`).

### PDF reports

```python
from seventhings.models import CreateReport

templates = client.reports.list_templates()
pdf: bytes = client.reports.create(CreateReport(templates[0].uuid, [obj_uuid]))
```

### Files

```python
with open("photo.jpg", "rb") as fh:
    file_uuid = client.files.upload("photo.jpg", fh)  # or pass bytes
meta = client.files.get(file_uuid)
data = client.files.get_data(file_uuid)
thumb = client.files.get_thumbnail(file_uuid)
recent = client.files.list()  # the most recent files (max 20)
```

### Tasks

```python
from seventhings.models import (
    CreateTask,
    TaskListOptions,
    TaskReferenceInput,
    TaskStatus,
    TimeInterval,
    TimeIntervalUnit,
    UpdateTask,
)

task_uuid = client.tasks.create(
    CreateTask(
        title="Inspect",
        deadline="2026-12-31",
        assignees=[user_uuid],
        references=[TaskReferenceInput(obj_uuid)],
        reminders=[TimeInterval(TimeIntervalUnit.DAYS, 1)],
    )
)
tasks = client.tasks.list(TaskListOptions(status=TaskStatus.OPEN))
client.tasks.update_status(task_uuid, TaskStatus.CLOSED)
client.tasks.update(task_uuid, UpdateTask(title="Inspect again", assignees=[user_uuid]))  # PUT
client.tasks.delete(task_uuid)
```

### Rental cases

```python
from seventhings.models import (
    CreateRentalCase,
    RentalCaseReferenceInput,
    RentalCaseRenter,
    RenterType,
)

rental_uuid = client.rentals.create(
    CreateRentalCase(
        title="Laptop loan",
        renter=RentalCaseRenter(RenterType.USER, user_uuid),
        references=[RentalCaseReferenceInput(obj_uuid)],
        issue_date="2026-01-01 09:00:00",
        due_date="2026-01-08 09:00:00",
        responsible_user_uuid=user_uuid,
    )
)
rental = client.rentals.get(rental_uuid)
for rc in client.rentals.all():
    print(rc.title, rc.status)
```

### Rooms and locations

These work like objects. The difference is that `patch` returns the updated record, and responses that come back as a `{uuid, fields}` envelope are flattened into a single dict for you.

```python
loc_uuid = client.locations.create({"name": "HQ"})
room_uuid = client.rooms.create({"name": "Office 1", "building_id": 1})
room = client.rooms.patch(room_uuid, {"name": "Office 1a"})
```

### Users and persons

```python
from seventhings.models import PersonListOptions, UserListOptions, UserSortBy, UserSortOrder

users = client.users.list(UserListOptions(sort_by=UserSortBy.EMAIL, order=UserSortOrder.ASC))
me = client.users.get_by_id(tok.user_id)

person_uuid = client.persons.create({"email": "ada@example.com", "first_name": "Ada"})
person = client.persons.get(person_uuid)
print(person.email, person.fields.get_str("cost_center"))  # every field is in person.fields
client.persons.patch(person_uuid, {"department": "IT"})
for p in client.persons.all(PersonListOptions(sort_by="last_name")):
    ...
```

### Field definitions

```python
from seventhings.models import AssetTrackingTemplate

defs = client.field_definitions.list(AssetTrackingTemplate.ASSET)
required = client.field_definitions.mandatory(AssetTrackingTemplate.ASSET)
missing = client.field_definitions.missing_mandatory_fields(AssetTrackingTemplate.ASSET, payload)
options = defs[0].field_type.allowed_values()  # dropdown values
```

### Circularity Hub

Items and orders in the Circularity Hub use integer IDs.

```python
from seventhings.models import AddObjectEntry, FilterObject, FilterOperator

suggestions = client.circularity_hub.suggest_category(
    FilterObject(filter={"uuid": {FilterOperator.IN: [obj_uuid]}})
)  # None when there are no suggestions
client.circularity_hub.add_objects({obj_uuid: AddObjectEntry("chairs", "25.00")})
for item in client.circularity_hub.all_items():
    ...
order_id = client.circularity_hub.create_order([1, 2])
order = client.circularity_hub.get_order(order_id)
```

### Raw requests

`request()` covers anything the SDK doesn't wrap:

```python
resp = client.request("GET", "objects", query="page=1&per_page=5")
print(resp.status_code, resp.json())
```

## Filtering and sorting

```python
from seventhings.models import ListOptions, SortDirection, gte, in_, like

opts = (
    ListOptions(page=1, per_page=50)
    .sort_by("name", SortDirection.ASC)
    .sort_by("created_at", SortDirection.DESC)
    .where(like("name", "Laptop"), in_("status", "active", "pending"), gte("price", "100"))
)
```

This produces the following query string (brackets are sent literally and only the values are escaped):

```
page=1&per_page=50&sort[name]=ASC&sort[created_at]=DESC&filter[name][like][]=Laptop&filter[status][in][]=active&filter[status][in][]=pending&filter[price][gte]=100
```

| Operator | Helper | Description |
|----------|--------|-------------|
| `eq` | `eq` | Equal |
| `neq` | `neq` | Not equal |
| `gt`, `gte` | `gt`, `gte` | Greater than (or equal) |
| `gt_or_null`, `gte_or_null` | `gt_or_null`, `gte_or_null` | Greater than (or equal), including null |
| `lt`, `lte` | `lt`, `lte` | Less than (or equal) |
| `lt_or_null`, `lte_or_null` | `lt_or_null`, `lte_or_null` | Less than (or equal), including null |
| `like` | `like` | Contains substring (multi-value) |
| `not_like` | `not_like` | Does not contain substring (multi-value) |
| `in` | `in_` | Value in set (multi-value) |
| `nin` | `nin` | Value not in set (multi-value) |

## Error handling

Every exception derives from `seventhings.SeventhingsError`:

| Exception | When |
|-----------|------|
| `APIError` | The API returned a status of 400 or higher |
| `NetworkError` | Connection failure, timeout or another transport error (wraps the `httpx` exception) |
| `DecodeError` | The response could not be decoded, e.g. invalid JSON or a missing `Location` header |

```python
from seventhings import APIError

try:
    client.objects.get("nonexistent")
except APIError as err:
    print(err.status_code, err.body)
    if err.is_not_found:  # also: is_unauthorized, is_forbidden, is_conflict,
        ...  # is_rate_limited, is_server_error, is_feature_inactive
```

`is_feature_inactive` is true when the endpoint's module (for example rentals) is not active on the instance.

## Pagination

`list()` methods fetch a single page. The `all()` iterators on objects, rooms, locations, rentals, users, persons and Circularity Hub items (`all_items()`) walk through every page:
- they ignore `opts.page`;
- they use `opts.per_page` as the page size, defaulting to 100;
- they stop at the first page that is shorter than the page size.

Tasks and files have no paging. History is paged manually.

## Scope and limitations

- **No automatic token refresh.** Call `client.auth.refresh(refresh_token)` yourself when the access token expires.
- **No automatic retry and no rate limiting.** Wrap calls yourself if you need either, or pass an `httpx` client that uses a retrying transport.
- **Dates are strings**, as the API sends them (`Y-m-d H:i:s`, UTC). `Fields.get_time()` parses them.
- **Unknown enum values** from newer API versions are kept as plain strings rather than raising an error.

## Development

```sh
uv sync
uv run pytest                       # unit tests; each one runs against both Client and AsyncClient
uv run ruff check . && uv run ruff format --check .
uv run mypy                         # strict
uv run python scripts/unasync.py    # regenerate the sync client after editing _async/client.py
```

The synchronous client (`src/seventhings/_sync/client.py`) is **generated** from `src/seventhings/_async/client.py`, so edit the async file and regenerate. CI runs `scripts/unasync.py --check`. Request building and response decoding live in `src/seventhings/_operations.py`, which does no I/O and is shared by both clients.

### Integration tests

The integration tests run against a live instance and create, then delete, their own test data:

```sh
cp .env.example .env   # fill in SEVENTHINGS_BASE_URL/USERNAME/PASSWORD/CLIENT_ID
scripts/run-integration.sh            # or: uv run pytest -m integration
scripts/run-integration.sh -k person  # forward pytest args
```

`examples/demo.py` walks through the SDK end to end and uses the same environment variables.

## License

MIT
