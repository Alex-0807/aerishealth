import { describe, expect, it } from 'vitest'
import { toProduct } from '../api/productApi'
import { productDto } from '../test/fixtures'
import { matchingSkus, optionValueAvailability, resolveVariant } from './resolveVariant'

const product = toProduct(productDto())

describe('resolveVariant', () => {
  it('resolves a complete, in-stock selection to its SKU', () => {
    const result = resolveVariant(product, { colour: 'Blue', size: 'M' })

    expect(result.status).toBe('available')
    expect(result.status === 'available' && result.sku).toMatchObject({
      id: 'TEE-BLU-M',
      priceCents: 3190,
      availableQuantity: 4,
      imageUrl: '/static/images/tee-blue.svg',
    })
  })

  it('reports which dimensions are missing for an incomplete selection', () => {
    const result = resolveVariant(product, { colour: 'Blue' })

    expect(result).toEqual({ status: 'incomplete', missing: [product.options[1]] })
  })

  it('treats an explicitly cleared value as not selected', () => {
    expect(resolveVariant(product, { colour: 'Blue', size: undefined }).status).toBe('incomplete')
  })

  it('distinguishes a non-existent combination from an out-of-stock SKU', () => {
    expect(resolveVariant(product, { colour: 'Blue', size: 'XL' })).toEqual({ status: 'unavailable' })

    const outOfStock = resolveVariant(product, { colour: 'Blue', size: 'S' })
    expect(outOfStock.status).toBe('out_of_stock')
    expect(outOfStock.status === 'out_of_stock' && outOfStock.sku.id).toBe('TEE-BLU-S')
  })
})

describe('optionValueAvailability', () => {
  it('marks values that cannot combine with the other selections as impossible', () => {
    expect(optionValueAvailability(product.skus, { colour: 'Blue' }, 'size', 'XL')).toBe('impossible')
    expect(optionValueAvailability(product.skus, { size: 'S' }, 'colour', 'Red')).toBe('impossible')
  })

  it('marks values whose only SKUs are out of stock as sold_out (still selectable)', () => {
    expect(optionValueAvailability(product.skus, { colour: 'Blue' }, 'size', 'S')).toBe('sold_out')
  })

  it('ignores the current value of the same dimension so the user can switch values', () => {
    // Black is selected; Red must still be judged on its own merits.
    expect(optionValueAvailability(product.skus, { colour: 'Black', size: 'M' }, 'colour', 'Red')).toBe('available')
  })

  it('considers everything available when nothing is selected', () => {
    expect(optionValueAvailability(product.skus, {}, 'size', 'XL')).toBe('available')
  })
})

describe('matchingSkus', () => {
  it('returns the SKUs compatible with a partial selection', () => {
    expect(matchingSkus(product.skus, { colour: 'Red' }).map((s) => s.id)).toEqual([
      'TEE-RED-M',
      'TEE-RED-L',
      'TEE-RED-XL',
    ])
  })
})
