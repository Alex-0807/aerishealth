import type { OptionDimension } from '../domain/product'
import type { OptionValueAvailability } from '../domain/resolveVariant'

interface Props {
  dimension: OptionDimension
  selectedValue: string | undefined
  availabilityOf: (value: string) => OptionValueAvailability
  onSelect: (value: string) => void
  disabled?: boolean
}

export function VariantSelector({ dimension, selectedValue, availabilityOf, onSelect, disabled = false }: Props) {
  return (
    <fieldset className="variant-selector">
      <legend>
        {dimension.label}
        {selectedValue ? <span className="variant-selector__current">: {selectedValue}</span> : null}
      </legend>
      <div className="variant-selector__options">
        {dimension.values.map((value) => {
          const availability = availabilityOf(value)
          const selected = selectedValue === value
          const suffix =
            availability === 'sold_out' ? ' (out of stock)' : availability === 'impossible' ? ' (unavailable)' : ''
          return (
            <button
              key={value}
              type="button"
              className="option"
              data-availability={availability}
              // Starts with the visible text, so voice-control "click S" still works.
              aria-label={`${value}${suffix}`}
              aria-pressed={selected}
              // Impossible combinations cannot be chosen. Sold-out ones can, so the
              // user can see that the variant exists but is out of stock.
              disabled={disabled || (availability === 'impossible' && !selected)}
              title={availability === 'impossible' ? `${value} is not available with your other selections` : undefined}
              onClick={() => onSelect(value)}
            >
              {value}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
