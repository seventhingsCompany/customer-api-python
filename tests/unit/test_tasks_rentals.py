from __future__ import annotations

import pytest

from seventhings import APIError
from seventhings.models import (
    CreateRentalCase,
    CreateTask,
    ListOptions,
    RentalCaseRenter,
    RenterType,
    TaskListOptions,
    TaskStatus,
    UpdateRentalCase,
    UpdateTask,
)

from .conftest import Harness

TASK = {"uuid": "t-1", "title": "Check", "status": "open", "assignees": [], "author": "u"}
RENTAL = {"uuid": "r-1", "status": "requested", "title": "Laptop", "renter": None}


def test_tasks_list_is_a_bare_array(h: Harness) -> None:
    h.respond(json_body=[TASK])
    tasks = h.call(lambda c: c.tasks.list(TaskListOptions(status=TaskStatus.OPEN)))
    assert tasks[0].uuid == "t-1"
    assert h.path() == "/task-management/tasks"
    assert h.query() == "status=open"


def test_task_crud(h: Harness) -> None:
    h.respond(201, headers={"Location": "/customer-api/v1/task-management/task/t-1"})
    h.respond(json_body=TASK)
    h.respond(204)
    h.respond(204)
    h.respond(204)
    assert h.call(lambda c: c.tasks.create(CreateTask(title="Check"))) == "t-1"
    assert h.call(lambda c: c.tasks.get("t-1")).title == "Check"
    h.call(lambda c: c.tasks.update("t-1", UpdateTask(title="New")))
    h.call(lambda c: c.tasks.update_status("t-1", TaskStatus.CLOSED))
    h.call(lambda c: c.tasks.delete("t-1"))
    assert [(r.method, h.path(i)) for i, r in enumerate(h.requests)] == [
        ("POST", "/task-management/task"),
        ("GET", "/task-management/task/t-1"),
        ("PUT", "/task-management/task/t-1"),
        ("PUT", "/task-management/task/t-1/status"),
        ("DELETE", "/task-management/task/t-1"),
    ]
    assert h.body(0)["title"] == "Check"
    assert h.body(2)["title"] == "New"
    assert h.body(3) == {"status": "closed"}


def test_task_history(h: Harness) -> None:
    h.respond(json_body={"items": [{"task_uuid": "t-1"}], "page": 1, "per_page": 50, "total": 1})
    assert h.call(lambda c: c.tasks.history("t-1")).items[0].task_uuid == "t-1"
    assert h.path() == "/task-management/task/t-1/history"


def test_task_get_not_found(h: Harness) -> None:
    h.respond(404, json_body={"message": "not found"})
    with pytest.raises(APIError) as info:
        h.call(lambda c: c.tasks.get("missing"))
    assert info.value.is_not_found


def test_rentals_list(h: Harness) -> None:
    h.respond(json_body={"items": [RENTAL]})
    rentals = h.call(lambda c: c.rentals.list(ListOptions(page=1)))
    assert rentals[0].title == "Laptop" and rentals[0].renter is None
    assert h.path() == "/rental-management/rental-cases"
    assert h.query() == "page=1"


def test_rental_crud(h: Harness) -> None:
    create = CreateRentalCase(
        title="Laptop",
        renter=RentalCaseRenter(RenterType.USER, "u-1"),
        issue_date="2026-01-01 00:00:00",
        due_date="2026-01-08 00:00:00",
        responsible_user_uuid="u-2",
    )
    h.respond(201, headers={"Location": "/rental-management/rental-case/r-1"})
    h.respond(json_body=RENTAL)
    h.respond(204)
    h.respond(204)
    h.respond(json_body={"items": [{"rental_case_uuid": "r-1"}], "total": 1})
    assert h.call(lambda c: c.rentals.create(create)) == "r-1"
    assert h.call(lambda c: c.rentals.get("r-1")).uuid == "r-1"
    update = UpdateRentalCase(
        title="Laptop 2", renter=None, issue_date="i", due_date="d", responsible_user_uuid="u"
    )
    h.call(lambda c: c.rentals.update("r-1", update))
    h.call(lambda c: c.rentals.delete("r-1"))
    hist = h.call(lambda c: c.rentals.history("r-1"))
    assert hist.items[0].rental_case_uuid == "r-1"
    assert [(r.method, h.path(i)) for i, r in enumerate(h.requests)] == [
        ("POST", "/rental-management/rental-case"),
        ("GET", "/rental-management/rental-case/r-1"),
        ("PUT", "/rental-management/rental-case/r-1"),
        ("DELETE", "/rental-management/rental-case/r-1"),
        ("GET", "/rental-management/rental-case/r-1/history"),
    ]
    assert h.body(0)["renter"] == {"type": "user", "value": "u-1"}
