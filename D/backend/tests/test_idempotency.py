import sqlite3
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.conftest import add_item, cart_quantity, stock_of


def test_same_key_performs_mutation_once_and_replays_response(client: TestClient, db: sqlite3.Connection) -> None:
    first = add_item(client, "TEE-BLU-M", 2, key="abc123")
    second = add_item(client, "TEE-BLU-M", 2, key="abc123")
    third = add_item(client, "TEE-BLU-M", 2, key="abc123")

    assert first.status_code == second.status_code == third.status_code == 201
    assert first.json() == second.json() == third.json()
    assert "idempotent-replayed" not in first.headers
    assert second.headers["idempotent-replayed"] == "true"
    assert stock_of(db, "TEE-BLU-M") == 2  # 4 - 2, only once
    assert cart_quantity(db, "TEE-BLU-M") == 2
    assert client.get("/api/cart").json()["total_quantity"] == 2


def test_different_keys_are_independent_operations(client: TestClient, db: sqlite3.Connection) -> None:
    add_item(client, "TEE-BLU-M", 1, key="op-1")
    add_item(client, "TEE-BLU-M", 1, key="op-2")

    assert cart_quantity(db, "TEE-BLU-M") == 2


def test_insufficient_stock_outcome_is_replayed_even_after_restock(
    client: TestClient, set_stock: Callable[[str, int], None]
) -> None:
    set_stock("TEE-BLU-M", 0)
    first = add_item(client, "TEE-BLU-M", 1, key="k")
    set_stock("TEE-BLU-M", 10)
    retry = add_item(client, "TEE-BLU-M", 1, key="k")

    # The key identifies one logical attempt; its answer does not change on retry.
    assert first.status_code == retry.status_code == 409
    assert retry.json() == first.json()
    assert retry.headers["idempotent-replayed"] == "true"


def test_reusing_key_with_different_payload_is_rejected(client: TestClient, db: sqlite3.Connection) -> None:
    add_item(client, "TEE-BLU-M", 1, key="k")

    res = add_item(client, "TEE-BLU-M", 3, key="k")

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert cart_quantity(db, "TEE-BLU-M") == 1


def test_missing_idempotency_key_is_rejected(client: TestClient, db: sqlite3.Connection) -> None:
    res = client.post("/api/cart/items", json={"sku_id": "TEE-BLU-M", "quantity": 1})

    assert res.status_code == 400
    assert res.json()["error"]["code"] == "MISSING_IDEMPOTENCY_KEY"
    assert stock_of(db, "TEE-BLU-M") == 4


def test_malformed_idempotency_key_is_rejected(client: TestClient) -> None:
    res = add_item(client, "TEE-BLU-M", 1, key="x" * 300)

    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_IDEMPOTENCY_KEY"


def test_failure_mid_transaction_rolls_back_everything_and_retry_succeeds(
    client: TestClient, db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Crash *after* the stock decrement and cart upsert, before the key is stored.

    Nothing may persist, otherwise stock would leak or a retry would double-add.
    """
    import pdp.idempotency

    real_save = pdp.idempotency.save
    monkeypatch.setattr(pdp.idempotency, "save", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk gone")))

    failed = add_item(client, "TEE-BLU-M", 1, key="retry-me")

    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "INTERNAL_ERROR"
    assert stock_of(db, "TEE-BLU-M") == 4
    assert cart_quantity(db, "TEE-BLU-M") == 0
    assert db.execute("SELECT COUNT(*) FROM idempotency_keys").fetchone()[0] == 0

    monkeypatch.setattr(pdp.idempotency, "save", real_save)
    retried = add_item(client, "TEE-BLU-M", 1, key="retry-me")

    assert retried.status_code == 201
    assert "idempotent-replayed" not in retried.headers
    assert stock_of(db, "TEE-BLU-M") == 3
    assert cart_quantity(db, "TEE-BLU-M") == 1
