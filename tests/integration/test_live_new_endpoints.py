"""Live integration tests, ported from customer-api-go/new_endpoints_integration_test.go.

Exercises the newer spec endpoints (history, barcode lookup, reports) using
existing instance data. Skipped unless SEVENTHINGS_BASE_URL,
SEVENTHINGS_USERNAME, SEVENTHINGS_PASSWORD and SEVENTHINGS_CLIENT_ID are set;
run explicitly with ``pytest -m integration``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

import pytest

from seventhings import APIError, AsyncClient, Client
from seventhings.models import (
    CreateReport,
    HistoryListOptions,
    HistoryResponse,
    ListOptions,
    PersonListOptions,
)

from .conftest import credentials

pytestmark = pytest.mark.integration

T = TypeVar("T")


def _live_entity_uuid(fields: dict[str, Any], key: str) -> str:
    for k in (key, "uuid"):
        value = fields.get(k)
        if isinstance(value, str) and value:
            return value
    raise AssertionError(f"list response has no {key} or uuid")


def _live_entity_uuids(items: list[dict[str, Any]], key: str) -> list[str]:
    return [_live_entity_uuid(item, key) for item in items]


def _verify_live_history(
    fetch: Callable[[str, HistoryListOptions | None], HistoryResponse[T]],
    *uuids: str,
) -> None:
    for uuid in uuids:
        assert uuid, "empty entity UUID"
        first = fetch(uuid, HistoryListOptions(page=1, per_page=1))
        assert first.page == 1
        assert first.per_page == 1
        assert first.total >= 0
        assert len(first.items) == min(first.total, 1)
        assert first.items is not None

        if first.total < 2:
            # The spec does not prescribe out-of-range behavior. The live API
            # clamps to the last page, so look for a valid second page instead.
            continue

        second = fetch(uuid, HistoryListOptions(page=2, per_page=1))
        assert second.page == 2
        assert second.per_page == 1
        assert second.total >= 2
        assert len(second.items) == 1

        # Compare with a two-entry page to verify the offset and ordering.
        combined = fetch(uuid, HistoryListOptions(page=1, per_page=2))
        want = [*first.items, *second.items]
        assert combined.page == 1
        assert combined.per_page == 2
        assert combined.items == want, (
            "separate history pages do not match a two-entry page "
            "(or history changed during the test)"
        )
        return
    # Validated first pages for every resource; none had multiple history entries.


# ---------------------------------------------------------------------------
# Objects — history
# ---------------------------------------------------------------------------


def test_object_history(client: Client) -> None:
    items = client.objects.list(ListOptions(page=1, per_page=10))
    if len(items) == 0:
        pytest.skip("instance has no objects")

    uuid = _live_entity_uuid(items[0], "asset_uuid")
    client.objects.get(uuid)  # existing ObjectGet endpoint succeeds for the same UUID

    _verify_live_history(client.objects.history, *_live_entity_uuids(items, "asset_uuid"))


# ---------------------------------------------------------------------------
# Objects — get by barcode
# ---------------------------------------------------------------------------


def test_object_get_by_barcode(client: Client) -> None:
    items = client.objects.list(ListOptions(page=1, per_page=10))
    for item in items:
        barcode = item.get("barcode")
        if not isinstance(barcode, str) or not barcode:
            continue
        got = client.objects.get_by_barcode(barcode)
        assert _live_entity_uuid(got, "asset_uuid") == _live_entity_uuid(item, "asset_uuid")
        return
    pytest.skip("sample contains no objects with a barcode")


# ---------------------------------------------------------------------------
# Rooms — history
# ---------------------------------------------------------------------------


def test_room_history(client: Client) -> None:
    items = client.rooms.list(ListOptions(page=1, per_page=10))
    if len(items) == 0:
        pytest.skip("instance has no rooms")

    _verify_live_history(client.rooms.history, *_live_entity_uuids(items, "room_uuid"))


# ---------------------------------------------------------------------------
# Locations — history
# ---------------------------------------------------------------------------


def test_location_history(client: Client) -> None:
    items = client.locations.list(ListOptions(page=1, per_page=10))
    if len(items) == 0:
        pytest.skip("instance has no locations")

    _verify_live_history(client.locations.history, *_live_entity_uuids(items, "location_uuid"))


# ---------------------------------------------------------------------------
# Persons — history
# ---------------------------------------------------------------------------


def test_person_history(client: Client) -> None:
    items = client.persons.list(PersonListOptions(per_page=10))
    if len(items.items) == 0:
        pytest.skip("instance has no persons")

    uuids = [person.uuid for person in items.items]
    _verify_live_history(client.persons.history, *uuids)


# ---------------------------------------------------------------------------
# Tasks — history
# ---------------------------------------------------------------------------


def test_task_history(client: Client) -> None:
    items = client.tasks.list()
    if len(items) == 0:
        pytest.skip("instance has no tasks")

    uuids = [task.uuid for task in items[:10]]
    _verify_live_history(client.tasks.history, *uuids)


# ---------------------------------------------------------------------------
# Rental cases — history
# ---------------------------------------------------------------------------


def test_rental_case_history(client: Client) -> None:
    try:
        items = client.rentals.list(ListOptions(page=1, per_page=10))
    except APIError as exc:
        if exc.is_feature_inactive:
            pytest.skip("Rentals module is not active on this instance")
        raise
    if len(items) == 0:
        pytest.skip("instance has no rental cases")

    uuids = [rental.uuid for rental in items]
    try:
        _verify_live_history(client.rentals.history, *uuids)
    except APIError as exc:
        if exc.is_feature_inactive:
            pytest.skip("Rentals module is not active on this instance")
        raise


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def test_report_templates_list(client: Client) -> None:
    templates = client.reports.list_templates()
    assert templates is not None


def test_report_create(client: Client) -> None:
    templates = client.reports.list_templates()
    if len(templates) == 0:
        pytest.skip("instance has no report templates")

    items = client.objects.list(ListOptions(page=1, per_page=10))
    if len(items) == 0:
        pytest.skip("instance has no objects")

    pdf = client.reports.create(
        CreateReport(
            report_template_uuid=templates[0].uuid,
            object_uuids=[_live_entity_uuid(items[0], "asset_uuid")],
        )
    )
    assert pdf.startswith(b"%PDF-"), "response is not a PDF"


# ---------------------------------------------------------------------------
# Async smoke test — exercises the async client against the live instance.
# ---------------------------------------------------------------------------


def test_async_smoke() -> None:
    url, username, password, client_id = credentials()

    async def run() -> None:
        async_client = await AsyncClient.with_credentials(url, username, password, client_id)
        try:
            ping = await async_client.ping()
            assert ping.status == "OK"

            items = await async_client.objects.list(ListOptions(page=1, per_page=10))
            if items:
                uuid = _live_entity_uuid(items[0], "asset_uuid")
                history = await async_client.objects.history(
                    uuid, HistoryListOptions(page=1, per_page=1)
                )
                assert history.page == 1
                assert history.per_page == 1
        finally:
            await async_client.aclose()

    asyncio.run(run())
