"""Live integration tests, ported from customer-api-go/upgrade_integration_test.go,
rate_limit_integration_test.go and retry_after_integration_test.go.

The CRUD tests create their own catalog items, objects, tasks and rentals and
delete them again. The thumbnail test leaves an uploaded image behind because
the API has no file-delete endpoint. Skipped unless the SEVENTHINGS_* variables
are set; run explicitly with ``pytest -m integration``.
"""

from __future__ import annotations

import struct
import threading
import time
import uuid as uuidlib
import zlib
from collections.abc import Callable, Iterator
from datetime import datetime
from itertools import pairwise

import httpx
import pytest

from seventhings import (
    DEFAULT_REQUESTS_PER_MINUTE,
    APIError,
    Client,
    RentalCaseRenterRequiredError,
)
from seventhings.models import (
    CreateRentalCase,
    CreateTask,
    ListOptions,
    RentalCaseReferenceInput,
    RentalCaseRenter,
    RenterType,
    TaskReferenceInput,
    TimeInterval,
    TimeIntervalUnit,
    UpdateRentalCase,
    UpdateTask,
    eq,
)

from .conftest import base_url, unique_suffix

pytestmark = pytest.mark.integration


@pytest.fixture
def cleanup() -> Iterator[Callable[[Callable[[], object]], None]]:
    """Register cleanup callbacks; they run in reverse order after the test."""
    callbacks: list[Callable[[], object]] = []
    yield callbacks.append
    errors = []
    for callback in reversed(callbacks):
        try:
            callback()
        except Exception as exc:
            errors.append(exc)
    assert not errors, f"cleanup failed: {errors}"


def _ignore_not_found(fn: Callable[[], object]) -> Callable[[], None]:
    def run() -> None:
        try:
            fn()
        except APIError as exc:
            if not exc.is_not_found:
                raise

    return run


def _create_object(client: Client, prefix: str) -> str:
    suffix = unique_suffix()
    return client.objects.create(
        {"inventory_name": f"sdk-{prefix}-{suffix}", "barcode": f"SDK-{prefix.upper()}-{suffix}"}
    )


def _first_user_uuid(client: Client) -> str:
    users = client.users.list()
    if not users.items:
        pytest.fail("no user available")
    return users.items[0].uuid


def test_catalog_items_crud(
    client: Client, cleanup: Callable[[Callable[[], object]], None]
) -> None:
    name = "sdk-catalog-" + unique_suffix()
    try:
        uuid = client.catalog_items.create({"catalog_object_inventory_name": name})
    except APIError as exc:
        if exc.is_forbidden:
            pytest.skip("product catalog feature or create permission unavailable")
        raise
    cleanup(_ignore_not_found(lambda: client.catalog_items.delete(uuid)))

    item = client.catalog_items.get(uuid)
    assert item.uuid == uuid
    assert item.fields.get("catalog_object_inventory_name") == name

    item.fields["catalog_object_inventory_name"] = name + "-updated"
    client.catalog_items.update(uuid, item.fields)
    item = client.catalog_items.get(uuid)
    assert item.fields.get("catalog_object_inventory_name") == name + "-updated"

    page = client.catalog_items.list(
        ListOptions(
            page=1, per_page=10, filters=[eq("catalog_object_inventory_name", name + "-updated")]
        )
    )
    assert [i.uuid for i in page.items] == [uuid]

    client.catalog_items.delete(uuid)
    with pytest.raises(APIError) as info:
        client.catalog_items.get(uuid)
    assert info.value.is_not_found


def test_catalog_items_read(client: Client) -> None:
    """Read-only: never edits existing catalog records."""
    try:
        page = client.catalog_items.list(ListOptions(page=1, per_page=1))
    except APIError as exc:
        if exc.is_forbidden:
            pytest.skip("product catalog feature or read permission unavailable")
        raise
    assert (page.page, page.per_page) == (1, 1)
    if not page.items:
        return
    item = page.items[0]
    assert item.uuid
    detail = client.catalog_items.get(item.uuid)
    assert detail.uuid == item.uuid


def _same_instant(got: str | None, want: str) -> bool:
    def parse(value: str) -> datetime:
        return datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)

    return got is not None and parse(got) == parse(want)


def test_timed_rental_crud(client: Client, cleanup: Callable[[Callable[[], object]], None]) -> None:
    empty = CreateRentalCase(
        title="x", renter=None, issue_date="", due_date="", responsible_user_uuid=""
    )
    with pytest.raises(RentalCaseRenterRequiredError):
        client.rentals.create(empty)

    object_uuid = _create_object(client, "timed-rental")
    cleanup(lambda: client.objects.delete(object_uuid))
    user_uuid = _first_user_uuid(client)
    renter = RentalCaseRenter(RenterType.PLAIN, "SDK integration test")
    refs = [RentalCaseReferenceInput(object_uuid)]
    issue, due = "2099-01-01T10:00:00+02:00", "2099-01-01T12:00:00+02:00"
    uuid = client.rentals.create(
        CreateRentalCase(
            title="sdk-timed-rental-" + unique_suffix(),
            renter=renter,
            references=refs,
            is_full_day=False,
            issue_at=issue,
            due_at=due,
            issue_date="2099-01-01",
            due_date="2099-01-01",
            responsible_user_uuid=user_uuid,
        )
    )
    cleanup(_ignore_not_found(lambda: client.rentals.delete(uuid)))

    def verify(want_issue: str, want_due: str, full_day: bool) -> None:
        rental = client.rentals.get(uuid)
        assert rental.is_full_day is full_day
        if full_day:
            assert (rental.issue_at, rental.due_at) == (None, None)
        else:
            assert _same_instant(rental.issue_at, want_issue), rental.issue_at
            assert _same_instant(rental.due_at, want_due), rental.due_at

    verify(issue, due, False)
    with pytest.raises(RentalCaseRenterRequiredError):
        client.rentals.update(
            uuid,
            UpdateRentalCase(
                title="x", renter=None, issue_date="", due_date="", responsible_user_uuid=""
            ),
        )
    verify(issue, due, False)

    new_due = "2099-01-01T13:00:00+02:00"
    timed = UpdateRentalCase(
        title="updated timed rental",
        renter=renter,
        references=refs,
        is_full_day=False,
        issue_at=issue,
        due_at=new_due,
        issue_date="2099-01-01",
        due_date="2099-01-01",
        responsible_user_uuid=user_uuid,
    )
    client.rentals.update(uuid, timed)
    verify(issue, new_due, False)

    full_day = UpdateRentalCase(
        title=timed.title,
        renter=renter,
        references=refs,
        is_full_day=True,
        issue_date="2099-01-01",
        due_date="2099-01-02",
        responsible_user_uuid=user_uuid,
    )
    client.rentals.update(uuid, full_day)
    verify("", "", True)
    client.rentals.delete(uuid)


def _png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    row = b"\x00" + bytes(rgb) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def _image_size(data: bytes) -> tuple[int, int]:
    """(width, height) of a PNG or JPEG image."""
    if data.startswith(b"\x89PNG"):
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    assert data.startswith(b"\xff\xd8"), "thumbnail is neither PNG nor JPEG"
    i = 2
    while i < len(data):
        marker, length = data[i + 1], struct.unpack(">H", data[i + 2 : i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        i += 2 + length
    raise AssertionError("no JPEG frame header")


def test_thumbnail_custom_size(client: Client) -> None:
    uuid = client.files.upload(
        f"sdk-thumbnail-{unique_suffix()}.png", _png(640, 480, (80, 140, 200))
    )
    # The API has no file-delete endpoint, so the upload stays on the instance.
    data = client.files.get_thumbnail(uuid, width=320, height=240)
    assert _image_size(data) == (320, 240)
    assert client.files.get_thumbnail(uuid, width=320, height=240) == data


def test_task_optional_reminders(
    client: Client, cleanup: Callable[[Callable[[], object]], None]
) -> None:
    assignees = [_first_user_uuid(client)]
    object_uuid = _create_object(client, "reminders")
    cleanup(lambda: client.objects.delete(object_uuid))
    refs = [TaskReferenceInput(object_uuid)]
    uuid = client.tasks.create(
        CreateTask(
            title="sdk-optional-reminders",
            deadline="2099-12-31",
            assignees=assignees,
            references=refs,
            notify=False,
        )
    )
    cleanup(lambda: client.tasks.delete(uuid))
    zero = TimeInterval(TimeIntervalUnit.DAYS, 0)
    for reminders in ([zero], [], None):
        client.tasks.update(
            uuid,
            UpdateTask(
                title="sdk-optional-reminders",
                deadline="2099-12-31",
                assignees=assignees,
                references=refs,
                reminders=reminders,
                notify=False,
            ),
        )
        task = client.tasks.get(uuid)
        if reminders is not None:
            assert task.reminders == reminders


def test_api_error_headers(client: Client) -> None:
    """Real error headers are retained (without deliberately overloading the API)."""
    with pytest.raises(APIError) as info:
        client.objects.get(str(uuidlib.uuid4()))
    assert info.value.is_not_found
    assert len(info.value.headers) > 0


@pytest.mark.parametrize(
    ("limit", "gap"), [(DEFAULT_REQUESTS_PER_MINUTE, 0.3), (400, 0.15)], ids=["default", "400"]
)
def test_rate_limit(limit: int, gap: float) -> None:
    url = base_url()
    starts: list[float] = []
    lock = threading.Lock()

    def record(request: httpx.Request) -> None:
        with lock:
            starts.append(time.monotonic())

    http = httpx.Client(timeout=30, event_hooks={"request": [record]})
    with http, Client(url, http_client=http, rate_limit=limit) as c:
        threads = [threading.Thread(target=c.ping) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    assert len(starts) == 3
    starts.sort()
    for a, b in pairwise(starts):
        assert b - a >= gap - 0.005, f"requests sent too close together: {b - a:.3f}s"
