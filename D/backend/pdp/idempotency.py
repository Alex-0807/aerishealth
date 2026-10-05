"""Storage of processed requests keyed by Idempotency-Key.

These helpers must be called inside the same write transaction as the business
mutation, so "stock reserved + cart updated + outcome recorded" commit (or roll
back) together.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from pdp.errors import ApiError, ErrorCode

_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,255}$")


@dataclass(frozen=True)
class StoredResponse:
    status_code: int
    body: dict[str, Any]
    replayed: bool = False


def validate_key(raw: str | None) -> str:
    if raw is None or raw.strip() == "":
        raise ApiError(400, ErrorCode.MISSING_IDEMPOTENCY_KEY, "The Idempotency-Key header is required")
    key = raw.strip()
    if not _KEY_PATTERN.match(key):
        raise ApiError(
            400,
            ErrorCode.INVALID_IDEMPOTENCY_KEY,
            "Idempotency-Key must be 1-255 characters of letters, digits, '.', '_', ':' or '-'",
        )
    return key


def fingerprint(payload: dict[str, Any]) -> str:
    """Hash of the canonical request so a key cannot be reused for a different request."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def load(conn: sqlite3.Connection, cart_id: str, key: str, request_hash: str) -> StoredResponse | None:
    row = conn.execute(
        "SELECT request_hash, status_code, response_body FROM idempotency_keys WHERE cart_id = ? AND key = ?",
        (cart_id, key),
    ).fetchone()
    if row is None:
        return None
    if row["request_hash"] != request_hash:
        raise ApiError(
            422,
            ErrorCode.IDEMPOTENCY_KEY_REUSED,
            "This Idempotency-Key was already used with a different request body",
        )
    return StoredResponse(row["status_code"], json.loads(row["response_body"]), replayed=True)


def save(conn: sqlite3.Connection, cart_id: str, key: str, request_hash: str, response: StoredResponse) -> None:
    conn.execute(
        "INSERT INTO idempotency_keys (cart_id, key, request_hash, status_code, response_body) VALUES (?, ?, ?, ?, ?)",
        (cart_id, key, request_hash, response.status_code, json.dumps(response.body)),
    )
