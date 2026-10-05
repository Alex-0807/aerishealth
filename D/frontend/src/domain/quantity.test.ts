import { describe, expect, it } from 'vitest'
import { clampQuantity, maxSelectableQuantity } from './quantity'

describe('quantity rules', () => {
  it('never exceeds stock and never drops below 1', () => {
    expect(clampQuantity(5, 2)).toBe(2)
    expect(clampQuantity(0, 2)).toBe(1)
    expect(clampQuantity(-3, 2)).toBe(1)
    expect(clampQuantity(2.7, 5)).toBe(2)
    expect(clampQuantity(Number.NaN, 5)).toBe(1)
  })

  it('caps the selectable maximum at the per-request server limit', () => {
    expect(maxSelectableQuantity(500)).toBe(99)
    expect(maxSelectableQuantity(3)).toBe(3)
    expect(maxSelectableQuantity(0)).toBe(0)
    expect(maxSelectableQuantity(undefined)).toBe(0)
  })
})
