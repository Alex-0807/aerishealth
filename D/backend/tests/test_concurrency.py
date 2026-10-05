"""Race-condition tests against a real HTTP server.

TestClient runs requests one at a time through an in-process portal, which
would hide real concurrency. Here we start uvicorn on a free port in a
background thread and fire genuinely parallel HTTP requests from separate
client threads. A threading.Barrier releases them at the same instant. Each
request is handled on its own FastAPI threadpool thread with its own SQLite
connection, which is the production setup.
"""

from __future__ import annotations

import socket
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
import uvicorn

from pdp.db import connect
from pdp.main import create_app
from tests.conftest import add_item, cart_quantity, stock_of

SKU = "TEE-BLK-L"  # seeded with exactly one unit


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server_url(db_path: str) -> Iterator[str]:
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(db_path), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.01)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def raw_db(db_path: str, server_url: str) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    yield conn
    conn.close()


def _race(base_url: str, requests: list[tuple[str, int, str]]) -> list[httpx.Response]:
    """Send all requests simultaneously, each from its own thread and HTTP connection."""
    barrier = threading.Barrier(len(requests))

    def send(req: tuple[str, int, str]) -> httpx.Response:
        sku_id, quantity, key = req
        with httpx.Client(base_url=base_url, timeout=30) as http:
            barrier.wait()
            return add_item(http, sku_id, quantity, key=key)

    with ThreadPoolExecutor(max_workers=len(requests)) as pool:
        return list(pool.map(send, requests))


def test_two_concurrent_requests_for_the_final_unit(server_url: str, raw_db: sqlite3.Connection) -> None:
    assert stock_of(raw_db, SKU) == 1

    responses = _race(server_url, [(SKU, 1, "buyer-a"), (SKU, 1, "buyer-b")])

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201, 409], [r.text for r in responses]
    loser = next(r for r in responses if r.status_code == 409)
    assert loser.json()["error"]["code"] == "INSUFFICIENT_STOCK"
    assert loser.json()["error"]["details"] == {"sku_id": SKU, "requested": 1, "available": 0}
    assert stock_of(raw_db, SKU) == 0
    assert cart_quantity(raw_db, SKU) == 1


def test_final_unit_race_repeated(server_url: str, raw_db: sqlite3.Connection) -> None:
    """A single race can pass by luck; repeating it makes an intermittent oversell visible."""
    for round_no in range(25):
        raw_db.execute("UPDATE skus SET quantity = 1 WHERE id = ?", (SKU,))
        raw_db.execute("DELETE FROM cart_items")

        responses = _race(server_url, [(SKU, 1, f"r{round_no}-a"), (SKU, 1, f"r{round_no}-b")])

        assert sorted(r.status_code for r in responses) == [201, 409], f"round {round_no}"
        assert stock_of(raw_db, SKU) == 0
        assert cart_quantity(raw_db, SKU) == 1


def test_many_buyers_never_oversell(server_url: str, raw_db: sqlite3.Connection) -> None:
    raw_db.execute("UPDATE skus SET quantity = 3 WHERE id = ?", (SKU,))

    responses = _race(server_url, [(SKU, 1, str(uuid.uuid4())) for _ in range(12)])

    assert sum(r.status_code == 201 for r in responses) == 3
    assert sum(r.status_code == 409 for r in responses) == 9
    assert stock_of(raw_db, SKU) == 0
    assert cart_quantity(raw_db, SKU) == 3


def test_concurrent_retries_with_same_key_mutate_once(server_url: str, raw_db: sqlite3.Connection) -> None:
    """E.g. a client that times out and retries while the first attempt is still in flight."""
    raw_db.execute("UPDATE skus SET quantity = 5 WHERE id = ?", (SKU,))

    responses = _race(server_url, [(SKU, 1, "same-key")] * 6)

    assert all(r.status_code == 201 for r in responses)
    assert len({r.text for r in responses}) == 1  # identical stored response
    assert sum(r.headers.get("idempotent-replayed") == "true" for r in responses) == 5
    assert stock_of(raw_db, SKU) == 4
    assert cart_quantity(raw_db, SKU) == 1
