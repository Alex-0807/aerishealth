import type { CartDto } from '../api/cartApi'
import type { ProductDto, SkuDto } from '../api/productApi'

const sku = (id: string, colour: string, size: string, price: number, qty: number, image: string): SkuDto => ({
  id,
  product_id: 'classic-tee',
  price_cents: price,
  available_quantity: qty,
  image_url: `/static/images/${image}`,
  options: { colour, size },
})

/** Mirrors the backend seed: Blue/XL and Red/S missing, Blue/S has zero stock. */
export function productDto(): ProductDto {
  return {
    id: 'classic-tee',
    name: 'Everyday Organic Tee',
    description: 'A mid-weight organic cotton tee.',
    currency: 'AUD',
    image_url: '/static/images/tee-default.svg',
    options: [
      { name: 'colour', label: 'Colour', values: ['Black', 'Blue', 'Red'] },
      { name: 'size', label: 'Size', values: ['S', 'M', 'L', 'XL'] },
    ],
    skus: [
      sku('TEE-BLK-S', 'Black', 'S', 2990, 5, 'tee-black.svg'),
      sku('TEE-BLK-M', 'Black', 'M', 2990, 3, 'tee-black.svg'),
      sku('TEE-BLK-L', 'Black', 'L', 2990, 1, 'tee-black.svg'),
      sku('TEE-BLK-XL', 'Black', 'XL', 3290, 2, 'tee-black.svg'),
      sku('TEE-BLU-S', 'Blue', 'S', 2990, 0, 'tee-blue.svg'),
      sku('TEE-BLU-M', 'Blue', 'M', 3190, 4, 'tee-blue.svg'),
      sku('TEE-BLU-L', 'Blue', 'L', 3190, 2, 'tee-blue.svg'),
      sku('TEE-RED-M', 'Red', 'M', 2790, 8, 'tee-red.svg'),
      sku('TEE-RED-L', 'Red', 'L', 2790, 6, 'tee-red.svg'),
      sku('TEE-RED-XL', 'Red', 'XL', 3090, 3, 'tee-red.svg'),
    ],
  }
}

export function emptyCartDto(): CartDto {
  return { items: [], total_quantity: 0, subtotal_cents: 0, currency: 'AUD' }
}
