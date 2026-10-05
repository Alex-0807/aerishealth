export interface OptionDimension {
  /** Machine name, e.g. "colour". Keys `Sku.options`. */
  name: string
  /** Display label, e.g. "Colour". */
  label: string
  values: string[]
}

export interface Sku {
  id: string
  productId: string
  priceCents: number
  availableQuantity: number
  imageUrl: string
  options: Readonly<Record<string, string>>
}

export interface Product {
  id: string
  name: string
  description: string
  currency: string
  imageUrl: string
  options: OptionDimension[]
  skus: Sku[]
}

/** Selected value per dimension name; a missing key means "not selected yet". */
export type SelectedOptions = Readonly<Partial<Record<string, string>>>

/** Must match the server's per-request maximum (pdp/errors.py MAX_QUANTITY). */
export const MAX_QUANTITY_PER_ADD = 99

export function formatMoney(cents: number, currency: string): string {
  return new Intl.NumberFormat('en-AU', { style: 'currency', currency }).format(cents / 100)
}

export function describeOptions(product: Product, options: Readonly<Record<string, string>>): string {
  return product.options
    .map((dim) => options[dim.name])
    .filter((v): v is string => v !== undefined)
    .join(' / ')
}
