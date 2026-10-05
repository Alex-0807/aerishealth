from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from pdp.db import connect
from pdp.main import create_app


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")


@pytest.fixture
def client(db_path: str) -> Iterator[TestClient]:
    # raise_server_exceptions=False so unexpected errors surface as the real 500 response.
    with TestClient(create_app(db_path), raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def db(db_path: str, client: TestClient) -> Iterator[sqlite3.Connection]:
    """Direct DB access for arranging state and asserting on it (client fixture creates the schema)."""
    conn = connect(db_path)
    yield conn
    conn.close()


@pytest.fixture
def set_stock(db: sqlite3.Connection) -> Callable[[str, int], None]:
    def _set(sku_id: str, quantity: int) -> None:
        db.execute("UPDATE skus SET quantity = ? WHERE id = ?", (quantity, sku_id))

    return _set


def stock_of(db: sqlite3.Connection, sku_id: str) -> int:
    return db.execute("SELECT quantity FROM skus WHERE id = ?", (sku_id,)).fetchone()[0]


def cart_quantity(db: sqlite3.Connection, sku_id: str) -> int:
    row = db.execute("SELECT quantity FROM cart_items WHERE sku_id = ?", (sku_id,)).fetchone()
    return row[0] if row else 0


def add_item(client: TestClient | httpx.Client, sku_id: str, quantity: int, key: str | None = None) -> httpx.Response:
    return client.post(
        "/api/cart/items",
        json={"sku_id": sku_id, "quantity": quantity},
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )
