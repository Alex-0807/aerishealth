from __future__ import annotations

import sqlite3
from typing import Any


def get_product(conn: sqlite3.Connection, product_id: str) -> dict[str, Any] | None:
    product = conn.execute(
        "SELECT id, name, description, currency, image_url FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if product is None:
        return None

    options: list[dict[str, Any]] = []
    for opt in conn.execute(
        "SELECT name, label FROM product_options WHERE product_id = ? ORDER BY position", (product_id,)
    ):
        values = [
            row["value"]
            for row in conn.execute(
                "SELECT value FROM product_option_values WHERE product_id = ? AND option_name = ? ORDER BY position",
                (product_id, opt["name"]),
            )
        ]
        options.append({"name": opt["name"], "label": opt["label"], "values": values})

    skus: dict[str, dict[str, Any]] = {}
    for row in conn.execute(
        "SELECT id, product_id, price_cents, quantity, image_url FROM skus WHERE product_id = ? ORDER BY id",
        (product_id,),
    ):
        skus[row["id"]] = {
            "id": row["id"],
            "product_id": row["product_id"],
            "price_cents": row["price_cents"],
            "available_quantity": row["quantity"],
            "image_url": row["image_url"],
            "options": {},
        }
    for row in conn.execute(
        "SELECT sku_id, option_name, value FROM sku_option_values WHERE product_id = ?", (product_id,)
    ):
        skus[row["sku_id"]]["options"][row["option_name"]] = row["value"]

    return {
        "id": product["id"],
        "name": product["name"],
        "description": product["description"],
        "currency": product["currency"],
        "image_url": product["image_url"],
        "options": options,
        "skus": list(skus.values()),
    }
