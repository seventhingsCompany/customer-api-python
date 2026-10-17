# seventhings Python SDK

[![PyPI](https://img.shields.io/pypi/v/seventhings-customer-api)](https://pypi.org/project/seventhings-customer-api/) [![CI](https://github.com/seventhingsCompany/customer-api-python/actions/workflows/ci.yml/badge.svg)](https://github.com/seventhingsCompany/customer-api-python/actions/workflows/ci.yml)

Python client for the seventhings Customer API (`/customer-api/v1`). It offers the same features as the [Go](https://github.com/seventhingsCompany/customer-api-go) and [PHP](https://github.com/seventhingsCompany/customer-api-php) SDKs (v1.5.0) and comes with both a synchronous and an asynchronous client.

Targets API description `v0.20143_c5f8b54b3_20261005`.

- Python 3.10+
- The only runtime dependency is [`httpx`](https://www.python-httpx.org/)
- Fully typed (`py.typed`), with dataclass models

## Installation

```sh
pip install seventhings-customer-api
# or
uv add seventhings-customer-api
```

The import name is `seventhings`.

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
    rate_limit=200,  # requests per minute; 0 or None disables throttling
)
```

### Rate limiting

Each client sends at most **200 requests per minute** by default, evenly spaced (one every 300 ms) without bursts. The first request goes out immediately. Authentication, uploads and downloads count towards the same limit. Waiting requests are admitted in order; with `AsyncClient`, a cancelled request leaves the queue without using up a slot. Separate client instances have separate limits.

```python
Client(base_url, rate_limit=100)  # override
Client(base_url, rate_limit=0)  # disable
```

`with_credentials()` accepts `rate_limit` too. The SDK does not retry HTTP 429 answers itself (see [Retry-After](#retry-after)).

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
thumb = client.files.get_thumbnail(file_uuid)  # 150 x 100
thumb = client.files.get_thumbnail(file_uuid, width=320, height=240)  # 1-2000 px each
recent = client.files.list()  # the most recent files (max 20)
```

A custom thumbnail size keeps the aspect ratio. The API creates and caches each new size, and once a file has a certain number of sizes it answers further new sizes with 422.

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

`reminders=None` (the default) leaves reminders out of the request, `reminders=[]` disables them, and a zero interval (`TimeInterval(TimeIntervalUnit.DAYS, 0)`) reminds on the deadline.

### Rental cases

```python
from seventhings.models import (
    CreateRentalCase,
    RentalCaseReferenceInput,
    RentalCaseRenter,
    RenterType,
    UpdateRentalCase,
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

# Updates are full replacements (PUT): send the complete desired state.
client.rentals.update(
    rental_uuid,
    UpdateRentalCase(
        title="Laptop loan",
        renter=RentalCaseRenter(RenterType.USER, user_uuid),
        references=[RentalCaseReferenceInput(obj_uuid)],
        issue_date="2026-01-01 09:00:00",
        due_date="2026-01-08 09:00:00",
        responsible_user_uuid=user_uuid,
        comment="Updated pickup instructions",
    ),
)
```

Timed rentals: set `is_full_day=False` with `issue_at` and `due_at` (RFC 3339 timestamps; the return time is exclusive). Leave all three as None to let the API infer the kind on create, or to keep the stored kind on update. Responses always include `is_full_day`, `issue_at` and `due_at`.

`create` and `update` need a `renter`. The API description marks it optional, but the server currently fails with HTTP 500 when it is missing, so the SDK raises `RentalCaseRenterRequiredError` before sending the request.

### Rooms and locations

These work like objects. The difference is that `patch` returns the updated record (or None if the API sends no body). Records are the flat field maps the API returns; no `{uuid, fields}` envelope is unwrapped.

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

Person records are flat field maps. `person.uuid` comes from `person_uuid` only, and `person.fields` holds the whole map, including custom fields and attachments.

### Product catalog

Needs the product catalog feature and the matching rights on the instance.

```python
from seventhings.models import ListOptions

page = client.catalog_items.list(ListOptions(page=1, per_page=25))
# page.items, page.page, page.per_page, page.total, page.sort
item = client.catalog_items.get(item_uuid)
item_uuid = client.catalog_items.create({"catalog_object_inventory_name": "Laptop"})
client.catalog_items.update(item_uuid, item.fields)
client.catalog_items.delete(item_uuid)
for item in client.catalog_items.all():
    ...
```

`update` is a PUT that replaces every field: fields you leave out are emptied. Server-maintained fields are ignored, so a field map you read can be sent back unchanged. Object field keys start with `catalog_object_`; catalog metadata keys have no prefix. Updating or deleting a catalog item leaves the objects created from it untouched.

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
| `RentalCaseRenterRequiredError` | A rental case create/update has no renter (raised before any request) |

```python
from seventhings import APIError

try:
    client.objects.get("nonexistent")
except APIError as err:
    print(err.status_code, err.body)
    if err.is_not_found:  # also: is_unauthorized, is_forbidden, is_conflict,
        ...  # is_rate_limited, is_server_error, is_feature_inactive
```

`is_feature_inactive` is true when the endpoint's module (for example rentals) is not active on the instance. `err.headers` holds a copy of the response headers; they are not part of the exception message.

### Retry-After

`APIError.retry_after(now=None)` parses the standard `Retry-After` header, given either as seconds or as an HTTP date, and returns a `timedelta`:

```python
from datetime import datetime, timezone

try:
    client.objects.list()
except APIError as err:
    if err.is_rate_limited:
        now = datetime.now(timezone.utc)
        delay = err.retry_after(now)
        if delay is not None:
            retry_at = now + delay  # requeue the operation no earlier than this
        else:
            ...  # header missing or invalid: use your own bounded backoff
```

A date in the past gives a zero delay. A missing, repeated or invalid header gives None. The helper also works for other statuses that send the header (for example 503). It does not sleep or retry: the SDK sends each request once, and your application decides whether a retry is safe.

## Pagination

`list()` methods fetch a single page. The `all()` iterators on objects, rooms, locations, rentals, users, persons, catalog items and Circularity Hub items (`all_items()`) walk through every page:
- they ignore `opts.page`;
- they use `opts.per_page` as the page size, defaulting to 100;
- they stop at the first page that is shorter than the page size.

Tasks and files have no paging. History is paged manually.

## Scope and limitations

- **No automatic token refresh.** Call `client.auth.refresh(refresh_token)` yourself when the access token expires.
- **No automatic retry.** Use `APIError.retry_after()` and your own retry policy, or pass an `httpx` client that uses a retrying transport. Requests are throttled to 200 per minute per client by default (see [Rate limiting](#rate-limiting)).
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

The integration tests run against a live instance and create, then delete, their own test data. Use a test instance: some tests create users or field definitions that cannot be deleted, the Circularity Hub order tests check out existing items, and uploaded files stay because the API has no file-delete endpoint.

```sh
cp .env.example .env   # fill in SEVENTHINGS_BASE_URL/USERNAME/PASSWORD/CLIENT_ID
scripts/run-integration.sh            # or: uv run pytest -m integration
scripts/run-integration.sh -k person  # forward pytest args
```

[`examples/demo/`](https://github.com/seventhingsCompany/customer-api-python/tree/main/examples/demo) walks through the SDK end to end and uses the same environment variables.

## License

MIT
