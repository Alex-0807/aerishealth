import type { Product } from '../domain/product'
import { requestJson } from './http'

/** Wire format (snake_case) — mapped once here so the rest of the app never sees it. */
export interface SkuDto {
  id: string
  product_id: string
  price_cents: number
  available_quantity: number
  image_url: string
  options: Record<string, string>
}

export interface ProductDto {
  id: string
  name: string
  description: string
  currency: string
  image_url: string
  options: { name: string; label: string; values: string[] }[]
  skus: SkuDto[]
}

export function toProduct(dto: ProductDto): Product {
  return {
    id: dto.id,
    name: dto.name,
    description: dto.description,
    currency: dto.currency,
    imageUrl: dto.image_url,
    options: dto.options.map((o) => ({ name: o.name, label: o.label, values: [...o.values] })),
    skus: dto.skus.map((s) => ({
      id: s.id,
      productId: s.product_id,
      priceCents: s.price_cents,
      availableQuantity: s.available_quantity,
      imageUrl: s.image_url,
      options: { ...s.options },
    })),
  }
}

export async function fetchProduct(productId: string): Promise<Product> {
  // no-store: stock changes constantly; never let the browser serve a cached copy.
  const dto = await requestJson<ProductDto>(`/api/products/${encodeURIComponent(productId)}`, { cache: 'no-store' })
  return toProduct(dto)
}
