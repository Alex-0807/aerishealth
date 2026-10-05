"""SQLite connection handling, schema and transaction helper.

Design notes
------------
* One connection per request. sqlite3 connections are cheap, and sharing one
  connection across threads would serialise everything through Python and hide
  real database-level concurrency behaviour.
* ``isolation_level=None`` disables the sqlite3 module's implicit transaction
  management so that we control BEGIN/COMMIT explicitly.
* Writes use ``BEGIN IMMEDIATE``: the write lock is taken at the start of the
  transaction instead of on the first write. Two writers can then never both
  hold a read snapshot and later fail (or deadlock) when upgrading to a write
  lock; the second simply waits (up to ``busy_timeout``) for the first to finish.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

BUSY_TIMEOUT_SECONDS = 10.0

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    currency    TEXT NOT NULL,
    image_url   TEXT NOT NULL
);

-- Option dimensions (e.g. colour, size) are data, not hard-coded columns.
CREATE TABLE IF NOT EXISTS product_options (
    product_id TEXT NOT NULL REFERENCES products(id),
    name       TEXT NOT NULL,
    label      TEXT NOT NULL,
    position   INTEGER NOT NULL,
    PRIMARY KEY (product_id, name)
);

CREATE TABLE IF NOT EXISTS product_option_values (
    product_id  TEXT NOT NULL,
    option_name TEXT NOT NULL,
    value       TEXT NOT NULL,
    position    INTEGER NOT NULL,
    PRIMARY KEY (product_id, option_name, value),
    FOREIGN KEY (product_id, option_name) REFERENCES product_options(product_id, name)
);

CREATE TABLE IF NOT EXISTS skus (
    id          TEXT PRIMARY KEY,
    product_id  TEXT NOT NULL REFERENCES products(id),
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    -- Last line of defence: even a buggy unconditional decrement cannot
    -- persist negative stock, it fails with an IntegrityError instead.
    quantity    INTEGER NOT NULL CHECK (quantity >= 0),
    image_url   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sku_option_values (
    sku_id      TEXT NOT NULL REFERENCES skus(id),
    product_id  TEXT NOT NULL,
    option_name TEXT NOT NULL,
    value       TEXT NOT NULL,
    PRIMARY KEY (sku_id, option_name),
    FOREIGN KEY (product_id, option_name, value)
        REFERENCES product_option_values(product_id, option_name, value)
);

-- No price column on purpose: prices are always read from skus.
CREATE TABLE IF NOT EXISTS cart_items (
    cart_id    TEXT NOT NULL,
    sku_id     TEXT NOT NULL REFERENCES skus(id),
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (cart_id, sku_id)
);

-- Stored outcome of each processed POST /api/cart/items, scoped to the cart.
CREATE TABLE IF NOT EXISTS idempotency_keys (
    cart_id       TEXT NOT NULL,
    key           TEXT NOT NULL,
    request_hash  TEXT NOT NULL,
    status_code   INTEGER NOT NULL,
    response_body TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (cart_id, key)
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(
        db_path,
        timeout=BUSY_TIMEOUT_SECONDS,  # sets SQLite's busy timeout
        isolation_level=None,  # we issue BEGIN/COMMIT ourselves
        check_same_thread=False,  # FastAPI may open/close it on different threadpool threads
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def write_transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a block atomically: COMMIT on success, ROLLBACK on any exception."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def init_db(db_path: str | Path, *, reset: bool = False) -> None:
    """Create the schema and seed it when empty. Safe to call on every startup."""
    from pdp.seed import seed  # local import avoids a cycle

    path = Path(db_path)
    if reset:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{path}{suffix}").unlink(missing_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect(path)
    try:
        # WAL lets readers (GET product/cart) proceed while a writer holds the lock.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        with write_transaction(conn):
            if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
                seed(conn)
    finally:
        conn.close()
