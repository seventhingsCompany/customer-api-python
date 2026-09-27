from __future__ import annotations

import pytest

from seventhings import DecodeError
from seventhings.models import AddObjectEntry, FilterObject, FilterOperator, ListOptions

from .conftest import Harness


def test_suggest_category(h: Harness) -> None:
    h.respond(json_body={"obj-1": "chairs"}).respond(json_body=[])
    f = FilterObject(filter={"uuid": {FilterOperator.IN: ["obj-1"]}})
    assert h.call(lambda c: c.circularity_hub.suggest_category(f)) == {"obj-1": "chairs"}
    assert h.path(0) == "/circularity-hub/suggest-category"
    assert h.body(0) == {"filter": {"uuid": {"in": ["obj-1"]}}}
    # The API answers [] when it has no suggestions.
    assert h.call(lambda c: c.circularity_hub.suggest_category(f)) is None


def test_suggest_rest_price(h: Harness) -> None:
    h.respond(json_body={"obj-1": "12.00"}).respond(json_body=[])
    assert h.call(lambda c: c.circularity_hub.suggest_rest_price({"obj-1": "chairs"})) == {
        "obj-1": "12.00"
    }
    assert h.path(0) == "/circularity-hub/suggest-rest-price"
    assert h.body(0) == {"obj-1": "chairs"}
    assert h.call(lambda c: c.circularity_hub.suggest_rest_price({})) is None


def test_add_objects(h: Harness) -> None:
    h.respond(204)
    h.call(lambda c: c.circularity_hub.add_objects({"obj-1": AddObjectEntry("chairs", "10")}))
    assert h.path() == "/circularity-hub/add-objects-to-circularity-hub"
    assert h.body() == {"obj-1": {"category": "chairs", "price": "10"}}


def test_items(h: Harness) -> None:
    h.respond(json_body={"items": [{"id": 1}]})
    h.respond(json_body={"id": 1, "title": "Chair"})
    h.respond(204)
    h.respond(204)
    assert h.call(lambda c: c.circularity_hub.list_items(ListOptions(per_page=5))) == [{"id": 1}]
    assert h.call(lambda c: c.circularity_hub.get_item(1))["title"] == "Chair"
    h.call(lambda c: c.circularity_hub.update_item(1, {"price": "5"}))
    h.call(lambda c: c.circularity_hub.delete_item(1))
    assert [(r.method, h.path(i)) for i, r in enumerate(h.requests)] == [
        ("GET", "/circularity-hub/items"),
        ("GET", "/circularity-hub/item/1"),
        ("PATCH", "/circularity-hub/item/1"),
        ("DELETE", "/circularity-hub/item/1"),
    ]
    assert h.query(0) == "per_page=5"
    assert h.body(2) == {"price": "5"}


def test_orders(h: Harness) -> None:
    order = {"id": 7, "order_number": "O-7", "total_price": 12.5, "completed": True}
    h.respond(json_body={"items": [order]})
    h.respond(201, headers={"Location-Id": "7"})
    h.respond(json_body=order)
    h.respond(204)
    orders = h.call(lambda c: c.circularity_hub.list_orders())
    assert orders[0].order_number == "O-7" and orders[0].completed
    assert h.call(lambda c: c.circularity_hub.create_order([1, 2])) == 7
    assert h.call(lambda c: c.circularity_hub.get_order(7)).total_price == 12.5
    h.call(lambda c: c.circularity_hub.update_order(7, {"completed": True}))
    assert [(r.method, h.path(i)) for i, r in enumerate(h.requests)] == [
        ("GET", "/circularity-hub/orders"),
        ("POST", "/circularity-hub/orders"),
        ("GET", "/circularity-hub/order/7"),
        ("PATCH", "/circularity-hub/order/7"),
    ]
    assert h.body(1) == [1, 2]


def test_create_order_requires_location_id(h: Harness) -> None:
    h.respond(201)
    with pytest.raises(DecodeError):
        h.call(lambda c: c.circularity_hub.create_order([1]))
