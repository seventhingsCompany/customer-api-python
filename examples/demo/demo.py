"""End-to-end walkthrough of the SDK against a live seventhings instance.

Creates (and deletes again) a few demo objects, a task, a person, a catalog
item and a timed rental. Uploaded files stay: the API has no file-delete endpoint.

    export SEVENTHINGS_BASE_URL=... SEVENTHINGS_USERNAME=... \\
           SEVENTHINGS_PASSWORD=... SEVENTHINGS_CLIENT_ID=...
    uv run python examples/demo/demo.py [--rate-limit N]

Set SEVENTHINGS_AUTH_CODE, SEVENTHINGS_CODE_VERIFIER and SEVENTHINGS_REDIRECT_URI
to log in with an OAuth authorization code + PKCE instead of username/password.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
import time
import zlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, NoReturn

from seventhings import DEFAULT_REQUESTS_PER_MINUTE, APIError, Client
from seventhings.models import (
    AssetTrackingTemplate,
    CreateRentalCase,
    CreateReport,
    CreateTask,
    Fields,
    FileAttachment,
    HistoryListOptions,
    HistoryResponse,
    ListOptions,
    PersonListOptions,
    RentalCase,
    RentalCaseReferenceInput,
    RentalCaseRenter,
    RenterType,
    SortDirection,
    TaskReferenceInput,
    TaskStatus,
    TimeInterval,
    TimeIntervalUnit,
    UpdateRentalCase,
    UpdateTask,
    UserSortOrder,
    eq,
    like,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=DEFAULT_REQUESTS_PER_MINUTE,
        help="requests per minute per client (0 disables throttling)",
    )
    args = parser.parse_args()
    base_url = require_env("SEVENTHINGS_BASE_URL")
    client_id = require_env("SEVENTHINGS_CLIENT_ID")

    try:
        run(base_url, client_id, args.rate_limit)
    except APIError as exc:
        delay = exc.retry_after() if exc.is_rate_limited else None
        if delay is not None:
            pf("Rate", f"HTTP 429: retry no earlier than {delay} from now; no automatic retry")
        fail(f"ERROR: {exc}")


def run(base_url: str, client_id: str, rate_limit: int) -> None:
    with Client(base_url, rate_limit=rate_limit) as c:
        # -- Auth ---------------------------------------------------------------
        section("Auth", "Logging in…")
        code = os.environ.get("SEVENTHINGS_AUTH_CODE")
        if code:
            tok = c.auth.login_authorization_code(
                code,
                require_env("SEVENTHINGS_CODE_VERIFIER"),
                require_env("SEVENTHINGS_REDIRECT_URI"),
                client_id,
            )
            pf("Auth", "Using OAuth authorization code + PKCE")
        else:
            tok = c.auth.login(
                require_env("SEVENTHINGS_USERNAME"),
                require_env("SEVENTHINGS_PASSWORD"),
                client_id,
            )
        pf("Auth", f"Logged in — user_id={tok.user_id}")
        if rate_limit > 0:
            pf("Rate", f"Limit: {rate_limit} requests/minute, evenly spaced; shared by all calls")
        else:
            pf("Rate", "Request throttling disabled")

        # -- Objects ------------------------------------------------------------
        section("Objects", "Listing objects…")
        objs = c.objects.list(ListOptions(page=1, per_page=5))
        pf("Objects", f"Listed {len(objs)} object(s) (first page, max 5)")

        ts = int(time.time() * 1000)
        new_obj: dict[str, Any] = {
            "inventory_name": "SDK Demo Object",
            "barcode": f"SDK-DEMO-{ts}",
        }
        missing = c.field_definitions.missing_mandatory_fields(AssetTrackingTemplate.ASSET, new_obj)
        if missing:
            pf("Objects", f"Heads up — instance requires unset mandatory field(s): {missing}")
        else:
            pf("Objects", "Payload satisfies all mandatory asset fields")

        obj_uuid = c.objects.create(new_obj)
        pf("Objects", f"Created object {obj_uuid}")

        by_barcode = c.objects.get_by_barcode(new_obj["barcode"])
        pf(
            "Objects",
            f"Found by barcode {new_obj['barcode']} — "
            f"inventory_name={by_barcode.get('inventory_name')}",
        )

        c.objects.patch(obj_uuid, {"inventory_name": "SDK Demo Object (updated)"})
        updated = c.objects.get(obj_uuid)
        pf("Objects", f"Patched object — inventory_name={updated.get('inventory_name')}")

        c.objects.archive(obj_uuid)
        pf("Objects", f"Archived object {obj_uuid}")
        c.objects.unarchive(obj_uuid)
        pf("Objects", f"Unarchived object {obj_uuid}")

        history_opts = HistoryListOptions(page=1, per_page=5)
        object_history = c.objects.history(obj_uuid, history_opts)
        print_history("Objects", object_history)
        for entry in object_history.items:
            pf("History", f"Object event: type={entry.get('type')} date={entry.get('date')}")
        if object_history.page * object_history.per_page < object_history.total:
            next_page = HistoryListOptions(
                page=object_history.page + 1, per_page=object_history.per_page
            )
            print_history("Objects", c.objects.history(obj_uuid, next_page))

        # -- Reports ------------------------------------------------------------
        section("Reports", "Listing PDF templates…")
        templates = c.reports.list_templates()
        pf("Reports", f"Found {len(templates)} template(s)")
        if templates:
            pdf = c.reports.create(CreateReport(templates[0].uuid, [obj_uuid]))
            pf("Reports", f"Rendered template {templates[0].name!r} — {len(pdf)} PDF bytes")
        else:
            pf("Reports", "Skipping generation: no PDF templates configured")

        c.objects.delete(obj_uuid)
        pf("Objects", f"Deleted object {obj_uuid}")
        expect_not_found("Objects", lambda: c.objects.get(obj_uuid))

        section("Objects", "Fetching last 5 changed assets (sorted + filtered)…")
        recent = c.objects.list(
            ListOptions(page=1, per_page=5).sort_by("updated_at", SortDirection.DESC)
        )
        pf("Objects", f"Got {len(recent)} recently changed asset(s):")
        for i, raw in enumerate(recent, 1):
            f = Fields(raw)
            pf(
                "Objects",
                f"  {i}. {f.get_str('inventory_name')} (updated_at={f.get_str('updated_at')})",
            )

        section("Objects", 'Filtering assets by name containing "SDK"…')
        filtered = c.objects.list(
            ListOptions(page=1, per_page=5).where(like("inventory_name", "SDK"))
        )
        pf("Objects", f"Got {len(filtered)} asset(s) matching filter:")
        for i, raw in enumerate(filtered, 1):
            pf("Objects", f"  {i}. {raw.get('inventory_name')}")

        section("Objects", "Iterating all assets via objects.all() (capped at 10)…")
        seen = 0
        for obj in c.objects.all(ListOptions(per_page=50)):
            uuid = resource_uuid(obj, "asset_uuid")
            pf("Objects", f"  • {obj.get_str('inventory_name')} ({uuid})")
            seen += 1
            if seen >= 10:
                break
        pf("Objects", f"Iterated {seen} asset(s) before stopping")

        # -- Files --------------------------------------------------------------
        section("Files", "Uploading file…")
        content = b"Hello from the seventhings Python SDK demo!\n"
        file_uuid = c.files.upload("demo.txt", content)
        pf("Files", f"Uploaded file {file_uuid} (demo.txt, {len(content)} bytes)")

        meta = c.files.get(file_uuid)
        pf("Files", f"File metadata — name={meta.name}, type={meta.type}, size={meta.size}")

        host_uuid = c.objects.create(
            {"inventory_name": "SDK Demo File Host", "barcode": f"SDK-FILE-{ts}"}
        )
        pf("Files", f"Created temp object {host_uuid} for file attachment")
        attachment = [FileAttachment("documents", file_uuid)]
        c.objects.add_files(host_uuid, attachment)
        pf("Files", f"Attached file {file_uuid} to object {host_uuid}")
        c.objects.remove_files(host_uuid, attachment)
        pf("Files", f"Removed file from object {host_uuid}")
        c.objects.delete(host_uuid)
        pf("Files", f"Deleted temp object {host_uuid}")

        # -- Tasks --------------------------------------------------------------
        section("Tasks", "Creating task…")
        me = c.users.get_by_id(tok.user_id)
        pf("Tasks", f"Current user UUID: {me.uuid}")

        task_obj_uuid = c.objects.create(
            {"inventory_name": "SDK Demo Task Target", "barcode": f"SDK-TASK-{ts}"}
        )
        pf("Tasks", f"Created reference object {task_obj_uuid}")

        deadline = (date.today() + timedelta(days=365)).isoformat()
        task_refs = [TaskReferenceInput(task_obj_uuid)]
        # Reminders are left out (None); notify=False avoids notifying the assignee.
        task_uuid = c.tasks.create(
            CreateTask(
                title="SDK Demo Task",
                deadline=deadline,
                assignees=[me.uuid],
                references=task_refs,
                notify=False,
            )
        )
        pf("Tasks", f"Created task {task_uuid} referencing object {task_obj_uuid}")
        for reminders in ([TimeInterval(TimeIntervalUnit.DAYS, 0)], []):
            c.tasks.update(
                task_uuid,
                UpdateTask(
                    title="SDK Demo Task",
                    deadline=deadline,
                    assignees=[me.uuid],
                    references=task_refs,
                    reminders=reminders,
                    notify=False,
                ),
            )
            task = c.tasks.get(task_uuid)
            if task.reminders != reminders:
                fail(f"[Tasks] Unexpected reminders: {task.reminders}")
            pf("Tasks", f"Verified reminders: {task.reminders} (empty disables reminders)")

        c.tasks.update_status(task_uuid, TaskStatus.CLOSED)
        pf("Tasks", "Updated task status to closed")
        print_history("Tasks", c.tasks.history(task_uuid, history_opts))

        c.tasks.delete(task_uuid)
        pf("Tasks", f"Deleted task {task_uuid}")
        expect_not_found("Tasks", lambda: c.tasks.get(task_uuid))

        c.objects.delete(task_obj_uuid)
        pf("Tasks", f"Deleted reference object {task_obj_uuid}")

        # -- Persons ------------------------------------------------------------
        section("Persons", "Counting and listing persons…")
        pf("Persons", f"persons.count() → {c.persons.count()} person(s)")

        persons = c.persons.list(
            PersonListOptions(page=1, per_page=5, sort_by="id", order=UserSortOrder.ASC)
        )
        pf("Persons", f"Got {len(persons.items)} person(s) (page 1, max 5):")
        for i, p in enumerate(persons.items, 1):
            name = f"{p.firstname or ''} {p.lastname or ''}".strip()
            pf("Persons", f"  {i}. id={p.id} uuid={p.uuid} {name} <{p.email}>")

        if persons.items:
            first = persons.items[0]
            by_uuid = c.persons.get(first.uuid)
            pf("Persons", f"persons.get({first.uuid}) → id={by_uuid.id} email={by_uuid.email}")
            by_id = c.persons.get_by_id(first.id)
            pf("Persons", f"persons.get_by_id({first.id}) → uuid={by_id.uuid} email={by_id.email}")

        person_defs = c.field_definitions.mandatory(AssetTrackingTemplate.PERSON)
        if person_defs:
            keys = [d.field_key for d in person_defs]
            pf("Persons", f"Instance-required person field(s): {keys}")
        else:
            pf("Persons", "No custom mandatory person fields configured")

        email = f"sdk.demo+{ts}@example.com"
        person_uuid = c.persons.create({"email": email, "first_name": "SDK", "last_name": "Demo"})
        pf("Persons", f"Created person {person_uuid} <{email}>")

        c.persons.patch(person_uuid, {"department": "IT"})
        pf("Persons", f"Patched person {person_uuid} (department=IT)")
        person_history = c.persons.history(person_uuid, history_opts)
        print_history("Persons", person_history)
        for event in person_history.items:
            pf("History", f"Person event: {event.event_name} at {event.occurred_at}")

        c.persons.delete(person_uuid)
        pf("Persons", f"Deleted person {person_uuid}")
        expect_not_found("Persons", lambda: c.persons.get(person_uuid))

        # -- New API features (temporary resources, cleaned up on error) -------
        demo_catalog(c)
        demo_timed_rental(c, me.uuid)
        demo_thumbnail(c)

        # -- History of existing resources -------------------------------------
        section("History", "Reading history for existing resources…")
        sample = ListOptions(page=1, per_page=1)
        rooms = c.rooms.list(sample)
        if rooms:
            uuid = resource_uuid(rooms[0], "room_uuid")
            print_history("Rooms", c.rooms.history(uuid, history_opts))
        else:
            pf("History", "Skipping room history: no rooms available")
        locations = c.locations.list(sample)
        if locations:
            uuid = resource_uuid(locations[0], "location_uuid")
            print_history("Locations", c.locations.history(uuid, history_opts))
        else:
            pf("History", "Skipping location history: no locations available")
        try:
            rentals = c.rentals.list(sample)
        except APIError as exc:
            if not exc.is_feature_inactive:
                raise
            rentals = []
            pf("History", "Rentals module is not active on this instance")
        if rentals:
            print_history("Rentals", c.rentals.history(rentals[0].uuid, history_opts))
        else:
            pf("History", "Skipping rental history: no rental cases available")

        # -- Revoke -------------------------------------------------------------
        section("Auth", "Revoking tokens…")
        c.auth.revoke_tokens()
        pf("Auth", "Tokens revoked")

    print("\nDone — all steps completed successfully.")


def demo_catalog(c: Client) -> None:
    section("Catalog", "Creating a temporary catalog item…")
    name = f"SDK Demo Catalog {time.time_ns()}"
    try:
        uuid = c.catalog_items.create({"catalog_object_inventory_name": name})
    except APIError as exc:
        if exc.is_forbidden:
            pf("Catalog", "Skipped: product catalog feature or create permission unavailable")
            return
        raise
    with cleanup(lambda: c.catalog_items.delete(uuid)) as done:
        item = c.catalog_items.get(uuid)
        if item.uuid != uuid or item.fields.get("catalog_object_inventory_name") != name:
            fail("[Catalog] create/read mismatch")
        # PUT replaces the entire state: send the read field map back, not a patch.
        item.fields["catalog_object_inventory_name"] = name + " updated"
        c.catalog_items.update(uuid, item.fields)
        item = c.catalog_items.get(uuid)
        if item.fields.get("catalog_object_inventory_name") != name + " updated":
            fail("[Catalog] update/read mismatch")
        page = c.catalog_items.list(
            ListOptions(page=1, per_page=5).where(
                eq("catalog_object_inventory_name", name + " updated")
            )
        )
        if [i.uuid for i in page.items] != [uuid]:
            fail("[Catalog] filtered list did not return the temporary item")
        pf("Catalog", f"Verified create, get, PUT and filtered list — total={page.total}")
        c.catalog_items.delete(uuid)
        done()
        expect_not_found("Catalog", lambda: c.catalog_items.get(uuid))


def demo_timed_rental(c: Client, user_uuid: str) -> None:
    section("Rentals", "Creating and updating a timed rental…")
    object_uuid = c.objects.create(
        {"inventory_name": "SDK Demo Rental Target", "barcode": f"SDK-RENTAL-{time.time_ns()}"}
    )
    with cleanup(lambda: c.objects.delete(object_uuid)):
        # A future date with a non-UTC offset demonstrates UTC normalization.
        day = date.today() + timedelta(days=365)
        start = datetime(day.year, day.month, day.day, 10, tzinfo=timezone(timedelta(hours=2)))
        refs = [RentalCaseReferenceInput(object_uuid)]
        # Supply a renter: the current server returns 500 when it is omitted.
        renter = RentalCaseRenter(RenterType.PLAIN, "SDK Demo")
        uuid = c.rentals.create(
            CreateRentalCase(
                title="SDK Demo Timed Rental",
                renter=renter,
                references=refs,
                is_full_day=False,
                issue_at=start.isoformat(),
                due_at=(start + timedelta(hours=2)).isoformat(),
                issue_date=day.isoformat(),
                due_date=day.isoformat(),
                responsible_user_uuid=user_uuid,
            )
        )
        with cleanup(lambda: c.rentals.delete(uuid)):
            rental = c.rentals.get(uuid)
            verify_rental_times(rental, start, start + timedelta(hours=2))
            pf("Rentals", f"Verified timed rental {rental.issue_at} → {rental.due_at} (exclusive)")
            # Updates are full replacements: send the complete state.
            update = UpdateRentalCase(
                title="SDK Demo Timed Rental updated",
                renter=renter,
                references=refs,
                is_full_day=False,
                issue_at=start.isoformat(),
                due_at=(start + timedelta(hours=3)).isoformat(),
                issue_date=day.isoformat(),
                due_date=day.isoformat(),
                responsible_user_uuid=user_uuid,
            )
            c.rentals.update(uuid, update)
            verify_rental_times(c.rentals.get(uuid), start, start + timedelta(hours=3))
            full_day = UpdateRentalCase(
                title=update.title,
                renter=renter,
                references=refs,
                is_full_day=True,
                issue_date=day.isoformat(),
                due_date=(day + timedelta(days=1)).isoformat(),
                responsible_user_uuid=user_uuid,
            )
            c.rentals.update(uuid, full_day)
            rental = c.rentals.get(uuid)
            if not rental.is_full_day or rental.issue_at or rental.due_at:
                fail("[Rentals] full-day conversion did not clear rental times")
            pf("Rentals", "Verified extended return time and conversion to full-day")
    pf("Rentals", "Cleaned up rental and object")


def verify_rental_times(rental: RentalCase, issue: datetime, due: datetime) -> None:
    if rental.is_full_day or rental.issue_at is None or rental.due_at is None:
        fail("[Rentals] expected a timed rental with both timestamps")
    for raw, want in ((rental.issue_at, issue), (rental.due_at, due)):
        got = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
        if got != want:
            fail(f"[Rentals] timestamp {raw} does not match {want.isoformat()}")


def demo_thumbnail(c: Client) -> None:
    section("Files", "Uploading an image and verifying a custom thumbnail…")
    uuid = c.files.upload(f"sdk-demo-thumbnail-{time.time_ns()}.png", png(640, 480))
    pf("Files", f"Uploaded image {uuid}; it remains because the API has no delete endpoint")
    data = c.files.get_thumbnail(uuid, width=320, height=240)
    if image_size(data) != (320, 240):
        fail(f"[Files] thumbnail dimensions = {image_size(data)}, want (320, 240)")
    if c.files.get_thumbnail(uuid, width=320, height=240) != data:
        fail("[Files] cached thumbnail differs from first response")
    pf("Files", f"Verified 320x240 thumbnail and cached response ({len(data)} bytes)")


@contextmanager
def cleanup(remove: Callable[[], object]) -> Iterator[Callable[[], None]]:
    """Run ``remove`` on exit (also on errors) unless the yielded ``done()`` was called."""
    pending = [remove]
    try:
        yield pending.clear
    finally:
        for fn in pending:
            fn()


def png(width: int, height: int) -> bytes:
    """A minimal solid-colour RGB PNG."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(kind + data))
        return struct.pack(">I", len(data)) + kind + data + crc

    row = b"\x00" + bytes((80, 140, 200)) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def image_size(data: bytes) -> tuple[int, int]:
    """(width, height) of a PNG or JPEG image."""
    if data.startswith(b"\x89PNG"):
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    i = 2
    while data.startswith(b"\xff\xd8") and i + 9 <= len(data):
        marker, length = data[i + 1], struct.unpack(">H", data[i + 2 : i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        i += 2 + length
    fail("[Files] thumbnail is neither a PNG nor a JPEG")


def print_history(resource: str, page: HistoryResponse[Any]) -> None:
    pf(
        "History",
        f"{resource} — {len(page.items)} entries, page={page.page} "
        f"per_page={page.per_page} total={page.total}",
    )


def resource_uuid(fields: dict[str, Any], key: str) -> str:
    f = Fields(fields)
    uuid = f.get_str(key) or f.uuid
    if not uuid:
        fail(f"Resource is missing {key}/uuid")
    return uuid


def expect_not_found(tag: str, fetch: Any) -> None:
    try:
        fetch()
    except APIError as exc:
        if exc.is_not_found:
            pf(tag, "Confirmed deletion (404)")
            return
        fail(f"[{tag}] Expected 404 after deletion, got: {exc}")
    fail(f"[{tag}] Expected 404 after deletion, but the resource still exists")


def require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        fail(f"Missing required environment variable: {key}")
    return value


def fail(msg: str) -> NoReturn:
    print(msg, file=sys.stderr)
    sys.exit(1)


def section(tag: str, msg: str) -> None:
    print(f"\n── {tag} ──────────────────────────────────────────")
    pf(tag, msg)


def pf(tag: str, msg: str) -> None:
    print(f"[{tag:<7}] {msg}")


if __name__ == "__main__":
    main()
