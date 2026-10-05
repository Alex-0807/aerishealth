import sqlite3
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.conftest import add_item, cart_quantity, stock_of


def test_add_to_cart_success_reserves_stock(client: TestClient, db: sqlite3.Connection) -> None:
    res = add_item(client, "TEE-BLU-M", 2)

    assert res.status_code == 201
    body = res.json()
    assert body["sku"] == {"id": "TEE-BLU-M", "available_quantity": 2}
    assert body["cart"]["total_quantity"] == 2
    [line] = body["cart"]["items"]
    assert line["sku_id"] == "TEE-BLU-M"
    assert line["unit_price_cents"] == 3190
    assert line["line_total_cents"] == 6380
    assert stock_of(db, "TEE-BLU-M") == 2


def test_adding_same_sku_twice_accumulates_cart_line(client: TestClient) -> None:
    add_item(client, "TEE-RED-M", 1)
    res = add_item(client, "TEE-RED-M", 2)

    assert res.status_code == 201
    assert res.json()["cart"]["items"][0]["quantity"] == 3


def test_get_cart_returns_items_and_total_count(client: TestClient) -> None:
    assert client.get("/api/cart").json() == {"items": [], "total_quantity": 0, "subtotal_cents": 0, "currency": "AUD"}

    add_item(client, "TEE-RED-M", 2)
    add_item(client, "TEE-BLK-S", 1)
    cart = client.get("/api/cart").json()

    assert cart["total_quantity"] == 3
    assert [i["sku_id"] for i in cart["items"]] == ["TEE-RED-M", "TEE-BLK-S"]
    assert cart["subtotal_cents"] == 2 * 2790 + 2990


def test_client_supplied_price_and_stock_are_ignored(client: TestClient, db: sqlite3.Connection) -> None:
    res = client.post(
        "/api/cart/items",
        json={"sku_id": "TEE-BLU-M", "quantity": 1, "price_cents": 1, "available_quantity": 999},
        headers={"Idempotency-Key": "price-tamper"},
    )

    assert res.status_code == 201
    assert res.json()["cart"]["items"][0]["unit_price_cents"] == 3190
    assert stock_of(db, "TEE-BLU-M") == 3


@pytest.mark.parametrize("quantity", [0, -1, 100, 1.5, "2", True, None])
def test_invalid_quantity_is_rejected_without_side_effects(
    client: TestClient, db: sqlite3.Connection, quantity: object
) -> None:
    res = client.post(
        "/api/cart/items",
        json={"sku_id": "TEE-BLU-M", "quantity": quantity},
        headers={"Idempotency-Key": "bad-qty"},
    )

    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "INVALID_QUANTITY"
    assert error["details"]["min"] == 1 and error["details"]["max"] == 99
    assert stock_of(db, "TEE-BLU-M") == 4
    assert cart_quantity(db, "TEE-BLU-M") == 0


def test_missing_quantity_is_invalid_quantity(client: TestClient) -> None:
    res = client.post("/api/cart/items", json={"sku_id": "TEE-BLU-M"}, headers={"Idempotency-Key": "k"})

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "INVALID_QUANTITY"


def test_malformed_body_is_validation_error(client: TestClient) -> None:
    res = client.post("/api/cart/items", json={"quantity": 1}, headers={"Idempotency-Key": "k"})

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert res.json()["error"]["details"]["fields"][0]["field"] == "body.sku_id"


def test_nonexistent_sku_returns_404(client: TestClient) -> None:
    res = add_item(client, "TEE-PURPLE-XXL", 1)

    assert res.status_code == 404
    assert res.json() == {
        "error": {"code": "SKU_NOT_FOUND", "message": "SKU not found", "details": {"sku_id": "TEE-PURPLE-XXL"}}
    }


def test_nonexistent_combination_has_no_sku(client: TestClient) -> None:
    # Blue / XL is intentionally absent from the seed; any guessed id for it is unknown.
    assert add_item(client, "TEE-BLU-XL", 1).status_code == 404


def test_insufficient_stock_returns_409_with_details(
    client: TestClient, db: sqlite3.Connection, set_stock: Callable[[str, int], None]
) -> None:
    set_stock("TEE-BLU-M", 1)

    res = add_item(client, "TEE-BLU-M", 2)

    assert res.status_code == 409
    assert res.json() == {
        "error": {
            "code": "INSUFFICIENT_STOCK",
            "message": "Not enough stock",
            "details": {"sku_id": "TEE-BLU-M", "requested": 2, "available": 1},
        }
    }
    assert stock_of(db, "TEE-BLU-M") == 1
    assert cart_quantity(db, "TEE-BLU-M") == 0


def test_out_of_stock_sku_cannot_be_added(client: TestClient, db: sqlite3.Connection) -> None:
    res = add_item(client, "TEE-BLU-S", 1)  # seeded with quantity 0

    assert res.status_code == 409
    assert res.json()["error"]["details"]["available"] == 0
    assert stock_of(db, "TEE-BLU-S") == 0


def test_buying_exact_remaining_stock_succeeds_then_next_fails(client: TestClient, db: sqlite3.Connection) -> None:
    assert add_item(client, "TEE-BLK-XL", 2).status_code == 201
    assert add_item(client, "TEE-BLK-XL", 1).status_code == 409
    assert stock_of(db, "TEE-BLK-XL") == 0


def test_unexpected_failure_returns_internal_error(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: object, **__: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("pdp.cart.add_item", boom)

    res = add_item(client, "TEE-BLU-M", 1)

    assert res.status_code == 500
    assert res.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "boom" not in res.text  # internals are not leaked
