import { useMemo, useState } from 'react'
import { AddToCartButton } from '../components/AddToCartButton'
import { AddToCartFeedback } from '../components/AddToCartFeedback'
import { AvailabilityMessage } from '../components/AvailabilityMessage'
import { ProductGallery } from '../components/ProductGallery'
import { QuantitySelector } from '../components/QuantitySelector'
import { VariantSelector } from '../components/VariantSelector'
import type { Cart } from '../domain/cart'
import { describeOptions, formatMoney, type Product, type SelectedOptions } from '../domain/product'
import { clampQuantity, maxSelectableQuantity } from '../domain/quantity'
import {
  matchingSkus,
  optionValueAvailability,
  resolveVariant,
  selectedSkuOf,
  type VariantResolution,
} from '../domain/resolveVariant'
import { useAddToCart } from '../hooks/useAddToCart'

interface Props {
  product: Product
  refreshProduct: () => Promise<void>
  applyStock: (skuId: string, availableQuantity: number) => void
  setCart: (cart: Cart) => void
  refreshCart: () => Promise<void>
}

const maxFor = (variant: VariantResolution) =>
  variant.status === 'available' ? maxSelectableQuantity(variant.sku.availableQuantity) : 0

export function ProductDetails({ product, refreshProduct, applyStock, setCart, refreshCart }: Props) {
  // Only the user's *choices* are state. Everything else (SKU, price, image, stock,
  // max quantity) is derived on each render, so it can never be stale relative to
  // the selection or to refreshed product data.
  const [selected, setSelected] = useState<SelectedOptions>({})
  const [quantity, setQuantity] = useState(1)

  const variant = useMemo(() => resolveVariant(product, selected), [product, selected])
  const selectedSku = selectedSkuOf(variant)
  const maxQuantity = maxFor(variant)
  // Derived clamp protects against stock dropping underneath us (e.g. after a refresh).
  const effectiveQuantity = clampQuantity(quantity, maxQuantity)

  const addToCart = useAddToCart({
    onSuccess: (result) => {
      setCart(result.cart)
      applyStock(result.sku.id, result.sku.availableQuantity)
      void refreshProduct() // other SKUs may have changed too
    },
    onFailure: () => {
      // Whatever went wrong, our view of stock/cart may be stale: revalidate both.
      void refreshProduct()
      void refreshCart()
    },
  })
  const submitting = addToCart.state.status === 'submitting'

  function handleSelect(dimension: string, value: string) {
    const next = { ...selected, [dimension]: selected[dimension] === value ? undefined : value }
    setSelected(next)
    // Commit the clamp for the newly resolved SKU (5 on SKU A -> 2 on SKU B).
    setQuantity((q) => clampQuantity(q, maxFor(resolveVariant(product, next))))
    addToCart.reset()
  }

  function handleAdd() {
    if (variant.status !== 'available') return
    void addToCart.submit({
      skuId: variant.sku.id,
      quantity: effectiveQuantity,
      label: describeOptions(product, variant.sku.options),
    })
  }

  const candidates = selectedSku ? [selectedSku] : variant.status === 'incomplete' ? matchingSkus(product.skus, selected) : []
  const imageUrl = imageFor(candidates, product.imageUrl)
  const imageAlt = selectedSku
    ? `${product.name} in ${describeOptions(product, selectedSku.options)}`
    : product.name

  return (
    <article className="pdp">
      <ProductGallery imageUrl={imageUrl} alt={imageAlt} />

      <div className="pdp__info">
        <h1>{product.name}</h1>
        <p className="price" data-testid="price">
          {priceText(candidates, product.currency)}
        </p>
        <p className="description">{product.description}</p>

        {product.options.map((dimension) => (
          <VariantSelector
            key={dimension.name}
            dimension={dimension}
            selectedValue={selected[dimension.name]}
            availabilityOf={(value) => optionValueAvailability(product.skus, selected, dimension.name, value)}
            onSelect={(value) => handleSelect(dimension.name, value)}
            disabled={submitting}
          />
        ))}

        <AvailabilityMessage variant={variant} />

        <QuantitySelector
          value={effectiveQuantity}
          max={maxQuantity}
          onChange={setQuantity}
          disabled={submitting}
        />

        <AddToCartButton disabled={variant.status !== 'available'} submitting={submitting} onClick={handleAdd} />
        <AddToCartFeedback state={addToCart.state} onRetry={addToCart.retry} />
      </div>
    </article>
  )
}

/** Show a variant image only when it is unambiguous; otherwise the neutral product image. */
function imageFor(candidates: readonly { imageUrl: string }[], fallback: string): string {
  const urls = new Set(candidates.map((s) => s.imageUrl))
  const [only] = urls
  return urls.size === 1 && only ? only : fallback
}

function priceText(candidates: readonly { priceCents: number }[], currency: string): string {
  if (candidates.length === 0) return ''
  const prices = candidates.map((s) => s.priceCents)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  return min === max ? formatMoney(min, currency) : `${formatMoney(min, currency)} – ${formatMoney(max, currency)}`
}
