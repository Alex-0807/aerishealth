import type { OptionDimension, Product, SelectedOptions, Sku } from './product'

/**
 * Result of resolving the current option selection to a SKU.
 *
 * The three "not purchasable" cases are deliberately distinct:
 * - incomplete:  the user has not chosen a value for every dimension yet
 * - unavailable: every dimension is chosen but no SKU has that combination
 * - out_of_stock: the SKU exists but has zero stock
 */
export type VariantResolution =
  | { status: 'incomplete'; missing: OptionDimension[] }
  | { status: 'unavailable' }
  | { status: 'out_of_stock'; sku: Sku }
  | { status: 'available'; sku: Sku }

function matches(sku: Sku, selected: SelectedOptions, ignore?: string): boolean {
  return Object.entries(selected).every(
    ([name, value]) => name === ignore || value === undefined || sku.options[name] === value,
  )
}

export function resolveVariant(product: Pick<Product, 'options' | 'skus'>, selected: SelectedOptions): VariantResolution {
  const missing = product.options.filter((dim) => selected[dim.name] === undefined)
  if (missing.length > 0) return { status: 'incomplete', missing }

  const sku = product.skus.find((s) => product.options.every((dim) => s.options[dim.name] === selected[dim.name]))
  if (!sku) return { status: 'unavailable' }
  return sku.availableQuantity > 0 ? { status: 'available', sku } : { status: 'out_of_stock', sku }
}

export function selectedSkuOf(resolution: VariantResolution): Sku | undefined {
  return resolution.status === 'available' || resolution.status === 'out_of_stock' ? resolution.sku : undefined
}

/**
 * How a single option value relates to the *other* current selections.
 * - impossible: no SKU exists for it combined with the other selected values (disabled in the UI)
 * - sold_out:   SKUs exist but all of them have zero stock (still selectable, so the user can see "Out of stock")
 * - available:  at least one in-stock SKU
 */
export type OptionValueAvailability = 'available' | 'sold_out' | 'impossible'

export function optionValueAvailability(
  skus: readonly Sku[],
  selected: SelectedOptions,
  dimension: string,
  value: string,
): OptionValueAvailability {
  const candidates = skus.filter((s) => s.options[dimension] === value && matches(s, selected, dimension))
  if (candidates.length === 0) return 'impossible'
  return candidates.some((s) => s.availableQuantity > 0) ? 'available' : 'sold_out'
}

/** SKUs compatible with a (possibly partial) selection. */
export function matchingSkus(skus: readonly Sku[], selected: SelectedOptions): Sku[] {
  return skus.filter((s) => matches(s, selected))
}
