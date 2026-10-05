"""Seed data for the single demo product.

Deliberate edge cases (the frontend and tests rely on these):
* Blue / XL and Red / S do not exist at all       -> "combination unavailable"
* Blue / S exists but has quantity 0              -> "out of stock"
* Black / L has exactly one unit                  -> easy manual race-condition demo
* Prices and images differ between SKUs
"""

from __future__ import annotations

import argparse
import os
import sqlite3

PRODUCT_ID = "classic-tee"

PRODUCT = {
    "id": PRODUCT_ID,
    "name": "Everyday Organic Tee",
    "description": (
        "A mid-weight organic cotton tee with a relaxed fit. "
        "Pre-shrunk, garment-dyed and made to be worn every day."
    ),
    "currency": "AUD",
    "image_url": "/static/images/tee-default.svg",
}

OPTIONS = [
    ("colour", "Colour", ["Black", "Blue", "Red"]),
    ("size", "Size", ["S", "M", "L", "XL"]),
]

# (sku_id, colour, size, price_cents, quantity, image)
SKUS = [
    ("TEE-BLK-S", "Black", "S", 2990, 5, "tee-black.svg"),
    ("TEE-BLK-M", "Black", "M", 2990, 3, "tee-black.svg"),
    ("TEE-BLK-L", "Black", "L", 2990, 1, "tee-black.svg"),
    ("TEE-BLK-XL", "Black", "XL", 3290, 2, "tee-black.svg"),
    ("TEE-BLU-S", "Blue", "S", 2990, 0, "tee-blue.svg"),
    ("TEE-BLU-M", "Blue", "M", 3190, 4, "tee-blue.svg"),
    ("TEE-BLU-L", "Blue", "L", 3190, 2, "tee-blue.svg"),
    # Blue / XL intentionally missing
    # Red / S intentionally missing
    ("TEE-RED-M", "Red", "M", 2790, 8, "tee-red.svg"),
    ("TEE-RED-L", "Red", "L", 2790, 6, "tee-red.svg"),
    ("TEE-RED-XL", "Red", "XL", 3090, 3, "tee-red.svg"),
]


def seed(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO products (id, name, description, currency, image_url) VALUES (?, ?, ?, ?, ?)",
        (PRODUCT["id"], PRODUCT["name"], PRODUCT["description"], PRODUCT["currency"], PRODUCT["image_url"]),
    )
    for position, (name, label, values) in enumerate(OPTIONS):
        conn.execute(
            "INSERT INTO product_options (product_id, name, label, position) VALUES (?, ?, ?, ?)",
            (PRODUCT_ID, name, label, position),
        )
        conn.executemany(
            "INSERT INTO product_option_values (product_id, option_name, value, position) VALUES (?, ?, ?, ?)",
            [(PRODUCT_ID, name, value, i) for i, value in enumerate(values)],
        )

    seen_combinations: set[tuple[str, str]] = set()
    for sku_id, colour, size, price_cents, quantity, image in SKUS:
        if (colour, size) in seen_combinations:
            raise ValueError(f"Duplicate option combination {colour}/{size}")
        seen_combinations.add((colour, size))
        conn.execute(
            "INSERT INTO skus (id, product_id, price_cents, quantity, image_url) VALUES (?, ?, ?, ?, ?)",
            (sku_id, PRODUCT_ID, price_cents, quantity, f"/static/images/{image}"),
        )
        conn.executemany(
            "INSERT INTO sku_option_values (sku_id, product_id, option_name, value) VALUES (?, ?, ?, ?)",
            [(sku_id, PRODUCT_ID, "colour", colour), (sku_id, PRODUCT_ID, "size", size)],
        )


def main() -> None:
    from pdp.db import init_db
    from pdp.main import default_db_path

    parser = argparse.ArgumentParser(description="Create and seed the PDP database.")
    parser.add_argument("--reset", action="store_true", help="delete the existing database first")
    args = parser.parse_args()
    path = os.environ.get("PDP_DB_PATH") or default_db_path()
    init_db(path, reset=args.reset)
    print(f"Database ready at {path}")


if __name__ == "__main__":
    main()
