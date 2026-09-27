"""End-to-end walkthrough of the SDK against a live seventhings instance.

Creates (and deletes again) a few demo objects, a task, a file and a person.

    export SEVENTHINGS_BASE_URL=... SEVENTHINGS_USERNAME=... \\
           SEVENTHINGS_PASSWORD=... SEVENTHINGS_CLIENT_ID=...
    uv run python examples/demo/demo.py
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, NoReturn

from seventhings import APIError, Client
from seventhings.models import (
    AssetTrackingTemplate,
    CreateReport,
    CreateTask,
    Fields,
    FileAttachment,
    HistoryListOptions,
    HistoryResponse,
    ListOptions,
    PersonListOptions,
    SortDirection,
    TaskReferenceInput,
    TaskStatus,
    TimeInterval,
    TimeIntervalUnit,
    UserSortOrder,
    like,
)


def main() -> None:
    base_url = require_env("SEVENTHINGS_BASE_URL")
    username = require_env("SEVENTHINGS_USERNAME")
    password = require_env("SEVENTHINGS_PASSWORD")
    client_id = require_env("SEVENTHINGS_CLIENT_ID")

    with Client(base_url) as c:
        # -- Auth ---------------------------------------------------------------
        section("Auth", "Logging in…")
        tok = c.auth.login(username, password, client_id)
        pf("Auth", f"Logged in — user_id={tok.user_id}, token={tok.access_token[:20]}…")

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

        task_uuid = c.tasks.create(
            CreateTask(
                title="SDK Demo Task",
                deadline="2026-12-31",
                assignees=[me.uuid],
                references=[TaskReferenceInput(task_obj_uuid)],
                reminders=[TimeInterval(TimeIntervalUnit.DAYS, 1)],
            )
        )
        pf("Tasks", f"Created task {task_uuid} referencing object {task_obj_uuid}")

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
