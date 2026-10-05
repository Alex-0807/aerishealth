"""Pydantic models: request validation plus the response contract shown in /docs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from pdp.errors import MAX_QUANTITY, MIN_QUANTITY


class AddCartItemRequest(BaseModel):
    # Unknown fields (e.g. a client-supplied "price" or "stock") are ignored:
    # price and stock are only ever read from the database.
    model_config = ConfigDict(extra="ignore")

    sku_id: str = Field(min_length=1, max_length=64)
    # StrictInt rejects "2", 2.5 and true rather than silently coercing them.
    quantity: StrictInt = Field(ge=MIN_QUANTITY, le=MAX_QUANTITY)


class OptionDimension(BaseModel):
    name: str
    label: str
    values: list[str]


class Sku(BaseModel):
    id: str
    product_id: str
    price_cents: int
    available_quantity: int
    image_url: str
    options: dict[str, str]


class Product(BaseModel):
    id: str
    name: str
    description: str
    currency: str
    image_url: str
    options: list[OptionDimension]
    skus: list[Sku]


class CartItem(BaseModel):
    sku_id: str
    product_id: str
    product_name: str
    options: dict[str, str]
    image_url: str
    unit_price_cents: int
    quantity: int
    line_total_cents: int


class Cart(BaseModel):
    items: list[CartItem]
    total_quantity: int
    subtotal_cents: int
    currency: str


class SkuStock(BaseModel):
    id: str
    available_quantity: int


class AddCartItemResponse(BaseModel):
    cart: Cart
    sku: SkuStock


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any]


class ErrorResponse(BaseModel):
    error: ErrorDetail
