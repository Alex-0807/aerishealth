import { MAX_QUANTITY_PER_ADD } from './product'

/** Highest quantity the user may currently choose (0 = nothing purchasable). */
export function maxSelectableQuantity(availableQuantity: number | undefined): number {
  if (availableQuantity === undefined || availableQuantity <= 0) return 0
  return Math.min(availableQuantity, MAX_QUANTITY_PER_ADD)
}

/** Clamp to [1, max]. With max 0 the control is disabled, and 1 is only shown as a placeholder. */
export function clampQuantity(quantity: number, max: number): number {
  if (!Number.isFinite(quantity)) return 1
  return Math.max(1, Math.min(Math.trunc(quantity), Math.max(max, 1)))
}
