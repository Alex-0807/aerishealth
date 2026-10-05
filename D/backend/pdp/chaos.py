"""Opt-in fault injection for manually exercising the frontend's recovery paths.

Disabled unless one of these environment variables is set:
  PDP_CHAOS_LATENCY_MS   added delay before every /api request
  PDP_CHAOS_FAIL_RATE    0..1 probability that a POST /api/cart/items response
                         is replaced by a 503 *after* the handler committed,
                         simulating "the write succeeded but the response was lost".
                         A retry with the same Idempotency-Key must then replay.
"""

from __future__ import annotations

import asyncio
import os
import random
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from pdp.errors import ErrorCode, error_body


def install_chaos(app: FastAPI) -> None:
    latency_ms = int(os.environ.get("PDP_CHAOS_LATENCY_MS", "0"))
    fail_rate = float(os.environ.get("PDP_CHAOS_FAIL_RATE", "0"))
    if latency_ms <= 0 and fail_rate <= 0:
        return

    @app.middleware("http")
    async def chaos(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        if latency_ms > 0:
            await asyncio.sleep(latency_ms / 1000)
        response = await call_next(request)
        if request.method == "POST" and random.random() < fail_rate:
            return JSONResponse(
                status_code=503,
                content=error_body(ErrorCode.SERVICE_UNAVAILABLE, "Simulated lost response (chaos mode)"),
            )
        return response
