"""Structured errors: every failure leaves the API as {"error": {code, message, details}}."""

from __future__ import annotations

import logging
import sqlite3
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("pdp")

MIN_QUANTITY = 1
MAX_QUANTITY = 99


class ErrorCode(StrEnum):
    INVALID_QUANTITY = "INVALID_QUANTITY"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SKU_NOT_FOUND = "SKU_NOT_FOUND"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
    MISSING_IDEMPOTENCY_KEY = "MISSING_IDEMPOTENCY_KEY"
    INVALID_IDEMPOTENCY_KEY = "INVALID_IDEMPOTENCY_KEY"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


def error_body(code: ErrorCode, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code.value, "message": message, "details": details or {}}}


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.headers = headers


def _json(status_code: int, code: ErrorCode, message: str, details: dict[str, Any] | None = None,
          headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error_body(code, message, details), headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _json(exc.status_code, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        # Quantity problems get their own code so clients can react specifically.
        if any(err["loc"][:2] == ("body", "quantity") for err in errors):
            received = next((err.get("input") for err in errors if err["loc"][:2] == ("body", "quantity")), None)
            return _json(
                422,
                ErrorCode.INVALID_QUANTITY,
                f"Quantity must be a whole number between {MIN_QUANTITY} and {MAX_QUANTITY}",
                {"min": MIN_QUANTITY, "max": MAX_QUANTITY, "received": received if _is_json_scalar(received) else None},
            )
        fields = [{"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"]} for err in errors]
        return _json(422, ErrorCode.VALIDATION_ERROR, "Request validation failed", {"fields": fields})

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return _json(404, ErrorCode.NOT_FOUND, "Resource not found")
        if exc.status_code == 405:
            return _json(405, ErrorCode.METHOD_NOT_ALLOWED, "Method not allowed")
        return _json(exc.status_code, ErrorCode.INTERNAL_ERROR, str(exc.detail))

    @app.exception_handler(sqlite3.OperationalError)
    async def handle_db_busy(_: Request, exc: sqlite3.OperationalError) -> JSONResponse:
        # SQLite serialises writers; if the lock cannot be acquired within the
        # busy timeout we tell the client to retry (safe thanks to idempotency).
        if "locked" in str(exc) or "busy" in str(exc):
            logger.warning("database busy: %s", exc)
            return _json(503, ErrorCode.SERVICE_UNAVAILABLE, "The service is busy, please retry",
                         headers={"Retry-After": "1"})
        logger.exception("database error")
        return _json(500, ErrorCode.INTERNAL_ERROR, "An unexpected error occurred")

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", exc_info=exc)
        return _json(500, ErrorCode.INTERNAL_ERROR, "An unexpected error occurred")


def _is_json_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))
