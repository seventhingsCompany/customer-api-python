"""Live integration tests, ported from customer-api-go/integration_test.go.

Skipped unless SEVENTHINGS_BASE_URL, SEVENTHINGS_USERNAME, SEVENTHINGS_PASSWORD
and SEVENTHINGS_CLIENT_ID are set; run explicitly with ``pytest -m integration``.
"""

from __future__ import annotations

import contextlib

import pytest

from seventhings import APIError, Client
from seventhings.models import (
    AddObjectEntry,
    AssetTrackingTemplate,
    CreateFieldDefinition,
    CreateRentalCase,
    CreateTask,
    FieldDefinitionFieldType,
    FieldTypeName,
    FieldValueConstraint,
    FileAttachment,
    FilterObject,
    FilterOperator,
    ListOptions,
    PersonListOptions,
    RentalCaseReferenceInput,
    RentalCaseRenter,
    RenterType,
    TaskListOptions,
    TaskReferenceInput,
    TaskReferenceType,
    TaskStatus,
    TimeInterval,
    TimeIntervalUnit,
    UpdateFieldDefinition,
    UpdateRentalCase,
    UpdateTask,
    UserListOptions,
    UserSortBy,
    UserSortOrder,
    eq,
)

from .conftest import base_url, fresh_login, unique_suffix

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Ping
# ---------------------------------------------------------------------------


def test_ping() -> None:
    with Client(base_url()) as c:
        ping = c.ping()
    assert ping.status == "OK"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_auth(client: Client) -> None:
    assert client.token


def test_auth_refresh_and_revoke() -> None:
    client, tok = fresh_login()
    try:
        assert tok.refresh_token

        new_tok = client.auth.refresh(tok.refresh_token)
        assert new_tok.access_token
        assert client.token == new_tok.access_token

        client.auth.revoke_tokens()
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Objects — basic CRUD (existing)
# ---------------------------------------------------------------------------


def test_objects_crud(client: Client) -> None:
    uuid = client.objects.create(
        {
            "inventory_name": "integration-test-object",
            "barcode": "INT-TEST-" + unique_suffix(),
        }
    )
    try:
        obj = client.objects.get(uuid)
        assert obj["inventory_name"] == "integration-test-object"

        objects = client.objects.list(ListOptions(per_page=1))
        assert len(objects) > 0

        client.objects.patch(uuid, {"inventory_name": "updated-object"})
        updated = client.objects.get(uuid)
        assert updated["inventory_name"] == "updated-object"

        client.objects.delete(uuid)
        with pytest.raises(APIError):
            client.objects.get(uuid)
    finally:
        with contextlib.suppress(APIError):
            client.objects.delete(uuid)


# ---------------------------------------------------------------------------
# Objects — filters, sort, count
# ---------------------------------------------------------------------------


def test_objects_list_with_filters(client: Client) -> None:
    name = "filter-test-" + unique_suffix()
    uuid = client.objects.create(
        {"inventory_name": name, "barcode": "INT-FILTER-" + unique_suffix()}
    )
    try:
        objects = client.objects.list(
            ListOptions(per_page=10).where(eq("inventory_name", name)).sort_by("inventory_name")
        )
        assert len(objects) > 0
        for obj in objects:
            assert obj["inventory_name"] == name
    finally:
        with contextlib.suppress(APIError):
            client.objects.delete(uuid)


def test_objects_count(client: Client) -> None:
    count = client.objects.count()
    assert count >= 0

    # May be 0 on a fresh instance.
    client.objects.count(ListOptions().where(eq("inventory_name", "nonexistent-object-xyz")))


# ---------------------------------------------------------------------------
# Objects — archive / unarchive
# ---------------------------------------------------------------------------


def test_object_archive_unarchive(client: Client) -> None:
    uuid = client.objects.create(
        {
            "inventory_name": "archive-test-" + unique_suffix(),
            "barcode": "INT-ARCH-" + unique_suffix(),
        }
    )
    try:
        client.objects.archive(uuid)
        client.objects.unarchive(uuid)

        obj = client.objects.get(uuid)
        assert obj is not None
    finally:
        with contextlib.suppress(APIError):
            client.objects.unarchive(uuid)
        with contextlib.suppress(APIError):
            client.objects.delete(uuid)


# ---------------------------------------------------------------------------
# Objects — add/remove files
# ---------------------------------------------------------------------------


def test_object_files(client: Client) -> None:
    obj_uuid = client.objects.create(
        {
            "inventory_name": "file-test-" + unique_suffix(),
            "barcode": "INT-FILE-" + unique_suffix(),
        }
    )
    try:
        file_content = b"integration test file content"
        file_uuid = client.files.upload("test.txt", file_content)

        defs = client.field_definitions.list(AssetTrackingTemplate.ASSET)
        attachment_field_key = ""
        for d in defs:
            if d.field_type.name == FieldTypeName.ATTACHMENT:
                attachment_field_key = d.field_key
                break
        if not attachment_field_key:
            pytest.skip(
                "no ATTACHMENT field definition found on asset template; skipping file attach test"
            )

        attachment = FileAttachment(field_key=attachment_field_key, file_uuid=file_uuid)

        client.objects.add_files(obj_uuid, [attachment])
        client.objects.remove_files(obj_uuid, [attachment])
    finally:
        with contextlib.suppress(APIError):
            client.objects.delete(obj_uuid)


# ---------------------------------------------------------------------------
# Locations — full CRUD
# ---------------------------------------------------------------------------


def test_locations_crud(client: Client) -> None:
    name = "int-loc-" + unique_suffix()
    uuid = client.locations.create({"name": name})
    try:
        loc = client.locations.get(uuid)
        assert loc["name"] == name

        updated_name = "int-loc-updated-" + unique_suffix()
        client.locations.patch(uuid, {"name": updated_name})
        # Verify via GET since PATCH may return an empty body.
        loc_after_patch = client.locations.get(uuid)
        assert loc_after_patch["name"] == updated_name

        locations = client.locations.list(ListOptions(page=1, per_page=10))
        assert len(locations) > 0

        count = client.locations.count()
        assert count >= 1

        client.locations.delete(uuid)
        with pytest.raises(APIError):
            client.locations.get(uuid)
    finally:
        with contextlib.suppress(APIError):
            client.locations.delete(uuid)


# ---------------------------------------------------------------------------
# Rooms — full CRUD
# ---------------------------------------------------------------------------


def test_rooms_crud(client: Client) -> None:
    # A room requires a linked location (building_id). Find one first.
    locations = client.locations.list(ListOptions(page=1, per_page=1))
    if len(locations) == 0:
        pytest.skip("no locations available; skipping room CRUD (rooms require a building_id)")

    building_id = locations[0]["id"]

    room_fields: dict[str, object] = {
        "name": "int-room-" + unique_suffix(),
        "number": "IR-" + unique_suffix(),
        "building_id": building_id,
    }
    try:
        room_defs = client.field_definitions.mandatory(AssetTrackingTemplate.ROOM)
    except APIError:
        room_defs = []
    for d in room_defs:
        if d.field_key in room_fields:
            continue
        if d.field_type.name == FieldTypeName.DROPDOWN:
            allowed = d.field_type.allowed_values()
            if allowed:
                room_fields[d.field_key] = allowed[0]

    name = room_fields["name"]

    uuid = client.rooms.create(room_fields)
    try:
        room = client.rooms.get(uuid)
        assert room["name"] == name

        updated_name = "int-room-updated-" + unique_suffix()
        client.rooms.patch(uuid, {"name": updated_name})
        room_after_patch = client.rooms.get(uuid)
        assert room_after_patch["name"] == updated_name

        rooms = client.rooms.list(ListOptions(page=1, per_page=10))
        assert len(rooms) > 0

        count = client.rooms.count()
        assert count >= 1

        client.rooms.delete(uuid)
        with pytest.raises(APIError):
            client.rooms.get(uuid)
    finally:
        with contextlib.suppress(APIError):
            client.rooms.delete(uuid)


# ---------------------------------------------------------------------------
# Tasks — basic CRUD (existing)
# ---------------------------------------------------------------------------


def _first_user_uuid(client: Client) -> str:
    user_resp = client.users.list()
    assert len(user_resp.items) > 0, "expected at least 1 user"
    return user_resp.items[0].uuid


def test_tasks_crud(client: Client) -> None:
    user_uuid = _first_user_uuid(client)

    ref_uuid = client.objects.create(
        {
            "inventory_name": "integration-task-ref",
            "barcode": "INT-TASKREF-" + unique_suffix(),
        }
    )
    try:
        deadline = "2099-12-31"
        uuid = client.tasks.create(
            CreateTask(
                title="integration-test-task",
                deadline=deadline,
                assignees=[user_uuid],
                references=[TaskReferenceInput(uuid=ref_uuid, type=TaskReferenceType.ASSET)],
                reminders=[TimeInterval(unit=TimeIntervalUnit.DAYS, value=1)],
            )
        )
        try:
            task = client.tasks.get(uuid)
            assert task.title == "integration-test-task"

            tasks = client.tasks.list()
            assert len(tasks) > 0

            client.tasks.delete(uuid)
            with pytest.raises(APIError):
                client.tasks.get(uuid)
        finally:
            with contextlib.suppress(APIError):
                client.tasks.delete(uuid)
    finally:
        with contextlib.suppress(APIError):
            client.objects.delete(ref_uuid)


# ---------------------------------------------------------------------------
# Tasks — update
# ---------------------------------------------------------------------------


def test_task_update(client: Client) -> None:
    user_uuid = _first_user_uuid(client)

    ref_uuid = client.objects.create(
        {"inventory_name": "task-update-ref", "barcode": "INT-TUPD-" + unique_suffix()}
    )
    try:
        deadline = "2099-12-31"
        uuid = client.tasks.create(
            CreateTask(
                title="task-update-test",
                deadline=deadline,
                assignees=[user_uuid],
                references=[TaskReferenceInput(uuid=ref_uuid, type=TaskReferenceType.ASSET)],
                reminders=[TimeInterval(unit=TimeIntervalUnit.DAYS, value=1)],
            )
        )
        try:
            comment = "updated comment"
            client.tasks.update(
                uuid,
                UpdateTask(
                    title="task-update-test-renamed",
                    deadline=deadline,
                    assignees=[user_uuid],
                    references=[TaskReferenceInput(uuid=ref_uuid, type=TaskReferenceType.ASSET)],
                    reminders=[TimeInterval(unit=TimeIntervalUnit.DAYS, value=1)],
                    comment=comment,
                ),
            )

            updated = client.tasks.get(uuid)
            assert updated.title == "task-update-test-renamed"
            assert updated.comment == comment
        finally:
            with contextlib.suppress(APIError):
                client.tasks.delete(uuid)
    finally:
        with contextlib.suppress(APIError):
            client.objects.delete(ref_uuid)


# ---------------------------------------------------------------------------
# Tasks — status transition
# ---------------------------------------------------------------------------


def test_task_status_transition(client: Client) -> None:
    user_uuid = _first_user_uuid(client)

    ref_uuid = client.objects.create(
        {"inventory_name": "task-status-ref", "barcode": "INT-TSTAT-" + unique_suffix()}
    )
    try:
        deadline = "2099-12-31"
        uuid = client.tasks.create(
            CreateTask(
                title="task-status-test",
                deadline=deadline,
                assignees=[user_uuid],
                references=[TaskReferenceInput(uuid=ref_uuid, type=TaskReferenceType.ASSET)],
                reminders=[TimeInterval(unit=TimeIntervalUnit.DAYS, value=1)],
            )
        )
        try:
            client.tasks.update_status(uuid, TaskStatus.CLOSED)
            task = client.tasks.get(uuid)
            assert task.status == TaskStatus.CLOSED

            client.tasks.update_status(uuid, TaskStatus.OPEN)
            task = client.tasks.get(uuid)
            assert task.status == TaskStatus.OPEN
        finally:
            with contextlib.suppress(APIError):
                client.tasks.delete(uuid)
    finally:
        with contextlib.suppress(APIError):
            client.objects.delete(ref_uuid)


# ---------------------------------------------------------------------------
# Tasks — list with filters
# ---------------------------------------------------------------------------


def test_tasks_list_with_filters(client: Client) -> None:
    tasks = client.tasks.list(
        TaskListOptions(
            status=TaskStatus.OPEN,
            deadline_from="2000-01-01",
            deadline_to="2199-12-31",
            reference_type=TaskReferenceType.ASSET,
        )
    )
    # Result may be empty but the call should succeed.
    assert tasks is not None


# ---------------------------------------------------------------------------
# Rentals — full CRUD
# ---------------------------------------------------------------------------


def test_rentals_crud(client: Client) -> None:
    ref_uuid = client.objects.create(
        {
            "inventory_name": "rental-ref-" + unique_suffix(),
            "barcode": "INT-RENT-" + unique_suffix(),
        }
    )
    try:
        users_resp = client.users.list(UserListOptions(per_page=1))
        assert len(users_resp.items) > 0, "no users found for responsible_user_uuid"
        user_uuid = users_resp.items[0].uuid

        uuid = client.rentals.create(
            CreateRentalCase(
                title="Integration Test Rental",
                renter=RentalCaseRenter(type=RenterType.PLAIN, value="Integration Tester"),
                references=[RentalCaseReferenceInput(uuid=ref_uuid)],
                issue_date="2099-01-01",
                due_date="2099-06-01",
                comment="integration test rental",
                responsible_user_uuid=user_uuid,
                attachments=[],
            )
        )
        try:
            rental = client.rentals.get(uuid)
            assert rental.uuid == uuid

            client.rentals.update(
                uuid,
                UpdateRentalCase(
                    title="Updated Integration Test Rental",
                    renter=RentalCaseRenter(type=RenterType.PLAIN, value="Updated Tester"),
                    references=[RentalCaseReferenceInput(uuid=ref_uuid)],
                    issue_date="2099-01-01",
                    due_date="2099-06-01",
                    comment="updated rental comment",
                    responsible_user_uuid=user_uuid,
                    attachments=[],
                ),
            )

            cases = client.rentals.list(ListOptions(per_page=10))
            assert len(cases) > 0

            client.rentals.delete(uuid)
            with pytest.raises(APIError):
                client.rentals.get(uuid)
        finally:
            with contextlib.suppress(APIError):
                client.rentals.delete(uuid)
    finally:
        with contextlib.suppress(APIError):
            client.objects.delete(ref_uuid)


# ---------------------------------------------------------------------------
# Users — get by UUID, get by ID, list with options
# ---------------------------------------------------------------------------


def test_user_get_and_options(client: Client) -> None:
    resp = client.users.list(
        UserListOptions(page=1, per_page=5, sort_by=UserSortBy.EMAIL, order=UserSortOrder.ASC)
    )
    assert len(resp.items) > 0, "expected at least 1 user"

    user = resp.items[0]

    by_uuid = client.users.get(user.uuid)
    assert by_uuid.uuid == user.uuid

    by_id = client.users.get_by_id(user.id)
    assert by_id.id == user.id
    assert by_id.uuid == user.uuid


# ---------------------------------------------------------------------------
# Files — upload, get metadata, download data/thumbnail
# ---------------------------------------------------------------------------


def test_file_upload_and_download(client: Client) -> None:
    content = b"hello from integration test"
    file_uuid = client.files.upload("integration-test.txt", content)

    meta = client.files.get(file_uuid)
    assert meta.uuid == file_uuid
    assert meta.name == "integration-test.txt"

    data = client.files.get_data(file_uuid)
    assert len(data) > 0

    # Download thumbnail (may fail for non-image files, so we just check the
    # call doesn't raise unexpectedly hard).
    with contextlib.suppress(APIError):
        client.files.get_thumbnail(file_uuid)


# ---------------------------------------------------------------------------
# Files — basic list (existing)
# ---------------------------------------------------------------------------


def test_files_list(client: Client) -> None:
    files = client.files.list()
    assert files is not None  # may be empty


# ---------------------------------------------------------------------------
# Field Definitions — CRUD for asset and room templates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "template", [AssetTrackingTemplate.ASSET, AssetTrackingTemplate.ROOM], ids=str
)
def test_field_definitions_crud(client: Client, template: AssetTrackingTemplate) -> None:
    label = "int-test-field-" + unique_suffix()
    comment = ""

    uuid = client.field_definitions.create(
        template,
        CreateFieldDefinition(
            field_type=FieldDefinitionFieldType(
                name=FieldTypeName.TEXT,
                constraints=[FieldValueConstraint(type="max_length", value=255)],
            ),
            label=label,
            attributes=[],
            relations=[],
            comment=comment,
            default_value=None,
            possible_values=[],
        ),
    )

    definition = client.field_definitions.get(template, uuid)
    assert definition.label == label
    assert definition.field_type.name == FieldTypeName.TEXT

    updated_label = "int-test-field-updated-" + unique_suffix()
    client.field_definitions.update(
        template,
        uuid,
        UpdateFieldDefinition(
            uuid=definition.uuid,
            field_key=definition.field_key,
            field_type=FieldDefinitionFieldType(
                name=FieldTypeName.TEXT,
                constraints=[FieldValueConstraint(type="max_length", value=255)],
            ),
            label=updated_label,
            attributes=definition.attributes,
            relations=[],
            comment=comment,
            default_value=None,
            possible_values=[],
        ),
    )

    updated_def = client.field_definitions.get(template, uuid)
    assert updated_def.label == updated_label

    defs = client.field_definitions.list(template)
    assert len(defs) > 0


# ---------------------------------------------------------------------------
# Field Definitions — basic list (existing)
# ---------------------------------------------------------------------------


def test_field_definitions_list(client: Client) -> None:
    defs = client.field_definitions.list(AssetTrackingTemplate.ASSET)
    assert defs is not None


# ---------------------------------------------------------------------------
# Rentals — basic list (existing)
# ---------------------------------------------------------------------------


def test_rentals_list(client: Client) -> None:
    cases = client.rentals.list()
    assert cases is not None


# ---------------------------------------------------------------------------
# Locations — basic list (existing)
# ---------------------------------------------------------------------------


def test_locations_list(client: Client) -> None:
    locations = client.locations.list()
    assert locations is not None


# ---------------------------------------------------------------------------
# Rooms — basic list (existing)
# ---------------------------------------------------------------------------


def test_rooms_list(client: Client) -> None:
    rooms = client.rooms.list()
    assert rooms is not None


# ---------------------------------------------------------------------------
# Users — basic list (existing)
# ---------------------------------------------------------------------------


def test_users_list(client: Client) -> None:
    resp = client.users.list()
    assert len(resp.items) > 0


# ---------------------------------------------------------------------------
# CircularityHub — existing basic test
# ---------------------------------------------------------------------------


def test_circularity_hub(client: Client) -> None:
    items = client.circularity_hub.list_items(ListOptions(per_page=5))
    assert items is not None

    orders = client.circularity_hub.list_orders(ListOptions(per_page=5))
    assert orders is not None

    client.circularity_hub.suggest_category(FilterObject())


# ---------------------------------------------------------------------------
# CircularityHub — items CRUD
# ---------------------------------------------------------------------------


def test_circularity_hub_items_crud(client: Client) -> None:
    items = client.circularity_hub.list_items(ListOptions(per_page=1))
    if len(items) == 0:
        pytest.skip("no CircularityHub items available; skipping CRUD test")

    item_id = int(items[0]["id"])

    item = client.circularity_hub.get_item(item_id)
    assert item is not None

    client.circularity_hub.update_item(item_id, {})


# ---------------------------------------------------------------------------
# CircularityHub — orders CRUD
# ---------------------------------------------------------------------------


def test_circularity_hub_orders_crud(client: Client) -> None:
    items = client.circularity_hub.list_items(ListOptions(per_page=1))
    if len(items) == 0:
        pytest.skip("no CircularityHub items available; skipping orders CRUD test")

    item_id = int(items[0]["id"])

    order_id = client.circularity_hub.create_order([item_id])

    order = client.circularity_hub.get_order(order_id)
    assert order.id == order_id

    client.circularity_hub.update_order(order_id, {})


# ---------------------------------------------------------------------------
# CircularityHub — add objects
# ---------------------------------------------------------------------------


def test_circularity_hub_add_objects(client: Client) -> None:
    # purchasing_price is required for CHUB to process the object without an
    # "Array to string conversion" error.
    obj_uuid = client.objects.create(
        {
            "inventory_name": "ch-add-obj-" + unique_suffix(),
            "barcode": "INT-CHADD-" + unique_suffix(),
            "purchasing_price": 100.00,
        }
    )
    try:
        client.circularity_hub.add_objects(
            {obj_uuid: AddObjectEntry(category="category_furniture", price="10.00")}
        )
    finally:
        with contextlib.suppress(APIError):
            client.objects.delete(obj_uuid)


# ---------------------------------------------------------------------------
# CircularityHub — suggest rest price
# ---------------------------------------------------------------------------


def test_circularity_hub_suggest_rest_price(client: Client) -> None:
    # The endpoint may return an empty result depending on data, but should
    # not error.
    client.circularity_hub.suggest_rest_price({})


# ---------------------------------------------------------------------------
# Persons — list, get-by-uuid, get-by-id
# ---------------------------------------------------------------------------


def test_persons_list_and_get(client: Client) -> None:
    resp = client.persons.list(
        PersonListOptions(page=1, per_page=5, sort_by="id", order=UserSortOrder.ASC)
    )
    if len(resp.items) == 0:
        pytest.skip("no persons on instance; skipping get-by-uuid and get-by-id checks")

    first = resp.items[0]

    by_uuid = client.persons.get(first.uuid)
    assert by_uuid.uuid == first.uuid

    by_id = client.persons.get_by_id(first.id)
    assert by_id.id == first.id
    assert by_id.uuid == first.uuid


# ---------------------------------------------------------------------------
# Persons — count
# ---------------------------------------------------------------------------


def test_persons_count(client: Client) -> None:
    count = client.persons.count()
    assert count >= 0

    resp = client.persons.list()
    assert count == resp.total


# ---------------------------------------------------------------------------
# Persons — create + patch + create-user + delete
#
# The person created here is removed via persons.delete. Note:
# persons.create_user provisions a *user* account, and the customer API
# exposes no user-delete endpoint, so that user remains on the instance. Use a
# non-production instance for this test.
# ---------------------------------------------------------------------------


def test_person_create_and_create_user(client: Client) -> None:
    suffix = unique_suffix()
    email = f"sdk-int-{suffix}@example.test"

    person_fields: dict[str, object] = {
        "email": email,
        "first_name": "SDK",
        "last_name": "Integration " + suffix,
    }

    # Best-effort: discover any *real* mandatory person fields and synthesise
    # values. System-managed fields are excluded by field_definitions.mandatory.
    try:
        defs = client.field_definitions.mandatory(AssetTrackingTemplate.PERSON)
    except APIError:
        defs = []
    for d in defs:
        if d.field_key in person_fields:
            continue
        if d.field_type.name == FieldTypeName.DROPDOWN:
            allowed = d.field_type.allowed_values()
            if allowed:
                person_fields[d.field_key] = allowed[0]
        elif d.field_type.name in (FieldTypeName.TEXT, FieldTypeName.LONG_TEXT):
            person_fields[d.field_key] = "int-" + suffix
        else:
            pytest.skip(
                f"mandatory person field {d.field_key!r} of type {d.field_type.name!r} "
                "not auto-fillable"
            )

    uuid = client.persons.create(person_fields)
    assert uuid, "expected non-empty UUID from Location header"
    try:
        person = client.persons.get(uuid)
        assert person.email == email

        new_last = "Integration Patched " + suffix
        client.persons.patch(uuid, {"last_name": new_last})
        patched = client.persons.get(uuid)
        assert patched.lastname == new_last

        client.persons.create_user(FilterObject(filter={"email": {FilterOperator.EQ: email}}))

        client.persons.delete(uuid)
        with pytest.raises(APIError):
            client.persons.get(uuid)
    finally:
        with contextlib.suppress(APIError):
            client.persons.delete(uuid)
