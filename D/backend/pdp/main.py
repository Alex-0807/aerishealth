from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from pdp import cart, idempotency, products
from pdp.chaos import install_chaos
from pdp.db import connect, init_db
from pdp.errors import ApiError, ErrorCode, install_error_handlers
from pdp.schemas import AddCartItemRequest, AddCartItemResponse, Cart, ErrorResponse, Product

BACKEND_DIR = Path(__file__).resolve().parent.parent


def default_db_path() -> str:
    return str(BACKEND_DIR / "data" / "pdp.db")


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(get_conn)]

_errors: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse} for status in (400, 404, 409, 422, 500, 503)
}


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="Product Detail Page API", version="1.0.0")
    app.state.db_path = db_path or os.environ.get("PDP_DB_PATH") or default_db_path()
    init_db(app.state.db_path)

    install_error_handlers(app)
    install_chaos(app)
    app.mount("/static", StaticFiles(directory=BACKEND_DIR / "static"), name="static")

    @app.get("/api/products/{product_id}", response_model=Product, responses={404: _errors[404]})
    def read_product(product_id: str, conn: Conn) -> dict[str, Any]:
        product = products.get_product(conn, product_id)
        if product is None:
            raise ApiError(404, ErrorCode.PRODUCT_NOT_FOUND, "Product not found", {"product_id": product_id})
        return product

    @app.post(
        "/api/cart/items",
        status_code=201,
        response_model=AddCartItemResponse,
        responses=_errors,
    )
    def add_cart_item(
        payload: AddCartItemRequest,
        conn: Conn,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> JSONResponse:
        key = idempotency.validate_key(idempotency_key)
        result = cart.add_item(conn, sku_id=payload.sku_id, quantity=payload.quantity, idempotency_key=key)
        headers = {"Idempotent-Replayed": "true"} if result.replayed else None
        return JSONResponse(status_code=result.status_code, content=result.body, headers=headers)

    @app.get("/api/cart", response_model=Cart)
    def read_cart(conn: Conn) -> dict[str, Any]:
        return cart.get_cart(conn)

    return app

