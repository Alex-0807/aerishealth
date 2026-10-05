"""Cart read model and the stock-reserving add-to-cart operation."""

from __future__ import annotations

import sqlite3
from typing import Any

from pdp import idempotency
from pdp.db import write_transaction
from pdp.errors import ApiError, ErrorCode, error_body
from pdp.idempotency import StoredResponse

# Authentication is out of scope, so there is a single anonymous cart. Every
# query is still parameterised by cart_id so a per-session cart is a small change.
DEFAULT_CART_ID = "default"
DEFAULT_CURRENCY = "AUD"


def get_cart(conn: sqlite3.Connection, cart_id: str = DEFAULT_CART_ID) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT ci.sku_id, ci.quantity, s.product_id, s.price_cents, s.image_url,
               p.name AS product_name, p.currency
        FROM cart_items ci
        JOIN skus s ON s.id = ci.sku_id
        JOIN products p ON p.id = s.product_id
        WHERE ci.cart_id = ?
        ORDER BY ci.created_at, ci.sku_id
        """,
        (cart_id,),
    ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        options = {
            o["option_name"]: o["value"]
            for o in conn.execute("SELECT option_name, value FROM sku_option_values WHERE sku_id = ?", (row["sku_id"],))
        }
        items.append(
            {
                "sku_id": row["sku_id"],
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "options": options,
                "image_url": row["image_url"],
                # Price always comes from the skus table, never from the client.
                "unit_price_cents": row["price_cents"],
                "quantity": row["quantity"],
                "line_total_cents": row["price_cents"] * row["quantity"],
            }
        )

    return {
        "items": items,
        "total_quantity": sum(i["quantity"] for i in items),
        "subtotal_cents": sum(i["line_total_cents"] for i in items),
        "currency": rows[0]["currency"] if rows else DEFAULT_CURRENCY,
    }


def add_item(
    conn: sqlite3.Connection,
    *,
    sku_id: str,
    quantity: int,
    idempotency_key: str,
    cart_id: str = DEFAULT_CART_ID,
) -> StoredResponse:
    """Reserve stock and add it to the cart exactly once per idempotency key.

    Everything below runs in ONE ``BEGIN IMMEDIATE`` transaction:
      1. look up the key (replay if already processed)
      2. atomically decrement stock only if enough is left
      3. upsert the cart line
      4. store the response under the key
    Any exception rolls back all of it, so a retry with the same key starts clean.
    """
    request_hash = idempotency.fingerprint({"sku_id": sku_id, "quantity": quantity})

    with write_transaction(conn):
        # Checked inside the write transaction: a concurrent request with the
        # same key is blocked on the write lock until we commit, and then sees
        # our stored row here instead of performing the mutation a second time.
        stored = idempotency.load(conn, cart_id, idempotency_key, request_hash)
        if stored is not None:
            return stored

        if conn.execute("SELECT 1 FROM skus WHERE id = ?", (sku_id,)).fetchone() is None:
            # Not stored: nothing was executed, and the SKU might be created later.
            raise ApiError(404, ErrorCode.SKU_NOT_FOUND, "SKU not found", {"sku_id": sku_id})

        # The check and the decrement are a single statement, so no other
        # writer can change the stock between "is there enough?" and "take it".
        reserved = conn.execute(
            "UPDATE skus SET quantity = quantity - ? WHERE id = ? AND quantity >= ?",
            (quantity, sku_id, quantity),
        ).rowcount == 1

        available = conn.execute("SELECT quantity FROM skus WHERE id = ?", (sku_id,)).fetchone()["quantity"]

        if not reserved:
            response = StoredResponse(
                409,
                error_body(
                    ErrorCode.INSUFFICIENT_STOCK,
                    "Not enough stock",
                    {"sku_id": sku_id, "requested": quantity, "available": available},
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO cart_items (cart_id, sku_id, quantity) VALUES (?, ?, ?)
                ON CONFLICT (cart_id, sku_id) DO UPDATE SET
                    quantity = cart_items.quantity + excluded.quantity,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                (cart_id, sku_id, quantity),
            )
            response = StoredResponse(
                201,
                {"cart": get_cart(conn, cart_id), "sku": {"id": sku_id, "available_quantity": available}},
            )

        # The 409 is stored too: the request *was* processed, and a retry of the
        # same logical operation should get the same answer (Stripe-style semantics).
        idempotency.save(conn, cart_id, idempotency_key, request_hash, response)
        return response
