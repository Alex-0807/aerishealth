import type { AddToCartResult, Cart } from '../domain/cart'
import { requestJson } from './http'

export interface CartDto {
  items: {
    sku_id: string
    product_id: string
    product_name: string
    options: Record<string, string>
    image_url: string
    unit_price_cents: number
    quantity: number
    line_total_cents: number
  }[]
  total_quantity: number
  subtotal_cents: number
  currency: string
}

export interface AddToCartDto {
  cart: CartDto
  sku: { id: string; available_quantity: number }
}

export function toCart(dto: CartDto): Cart {
  return {
    items: dto.items.map((i) => ({
      skuId: i.sku_id,
      productId: i.product_id,
      productName: i.product_name,
      options: { ...i.options },
      imageUrl: i.image_url,
      unitPriceCents: i.unit_price_cents,
      quantity: i.quantity,
      lineTotalCents: i.line_total_cents,
    })),
    totalQuantity: dto.total_quantity,
    subtotalCents: dto.subtotal_cents,
    currency: dto.currency,
  }
}

export async function fetchCart(): Promise<Cart> {
  return toCart(await requestJson<CartDto>('/api/cart', { cache: 'no-store' }))
}

/**
 * Only the SKU id and quantity are sent. Price and stock are always the
 * server's business, so the client never sends them.
 */
export async function addCartItem(
  item: { skuId: string; quantity: number },
  idempotencyKey: string,
): Promise<AddToCartResult> {
  const dto = await requestJson<AddToCartDto>('/api/cart/items', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ sku_id: item.skuId, quantity: item.quantity }),
  })
  return { cart: toCart(dto.cart), sku: { id: dto.sku.id, availableQuantity: dto.sku.available_quantity } }
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
}
