import type { VariantResolution } from '../domain/resolveVariant'

function joinLabels(labels: string[]): string {
  return labels.length <= 1 ? (labels[0] ?? '') : `${labels.slice(0, -1).join(', ')} and ${labels.at(-1)}`
}

/** One message per resolution state, so the three "can't buy" cases never look alike. */
export function AvailabilityMessage({ variant }: { variant: VariantResolution }) {
  let text: string
  switch (variant.status) {
    case 'incomplete':
      text = `Please select a ${joinLabels(variant.missing.map((d) => d.label.toLowerCase()))}.`
      break
    case 'unavailable':
      text = 'This combination is unavailable. Please choose a different option.'
      break
    case 'out_of_stock':
      text = 'Out of stock'
      break
    case 'available':
      text =
        variant.sku.availableQuantity <= 3
          ? `In stock: only ${variant.sku.availableQuantity} left`
          : `In stock: ${variant.sku.availableQuantity} available`
      break
  }
  return (
    // Polite live region: screen readers announce availability as options change.
    <p className={`availability availability--${variant.status}`} aria-live="polite" data-testid="availability">
      {text}
    </p>
  )
}
