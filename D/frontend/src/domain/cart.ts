export interface CartItem {
  skuId: string
  productId: string
  productName: string
  options: Readonly<Record<string, string>>
  imageUrl: string
  unitPriceCents: number
  quantity: number
  lineTotalCents: number
}

export interface Cart {
  items: CartItem[]
  totalQuantity: number
  subtotalCents: number
  currency: string
}

export interface AddToCartResult {
  cart: Cart
  /** Authoritative stock for the SKU right after the reservation. */
  sku: { id: string; availableQuantity: number }
}
