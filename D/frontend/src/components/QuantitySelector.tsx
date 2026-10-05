import { useId, useState } from 'react'
import { clampQuantity } from '../domain/quantity'

interface Props {
  value: number
  max: number
  onChange: (value: number) => void
  disabled: boolean
}

export function QuantitySelector({ value, max, onChange, disabled }: Props) {
  const inputId = useId()
  const hintId = useId()
  // Allows the field to be temporarily empty while typing; any valid number is clamped immediately.
  const [draft, setDraft] = useState<string | null>(null)
  const isDisabled = disabled || max < 1

  return (
    <div className="quantity">
      <label htmlFor={inputId}>Quantity</label>
      <div className="quantity__controls">
        <button
          type="button"
          aria-label="Decrease quantity"
          disabled={isDisabled || value <= 1}
          onClick={() => onChange(clampQuantity(value - 1, max))}
        >
          −
        </button>
        <input
          id={inputId}
          type="number"
          inputMode="numeric"
          min={1}
          max={Math.max(max, 1)}
          value={draft ?? String(value)}
          disabled={isDisabled}
          aria-describedby={hintId}
          onChange={(e) => {
            const raw = e.target.value
            const parsed = Number(raw)
            if (raw.trim() === '' || !Number.isFinite(parsed)) {
              setDraft(raw)
              return
            }
            setDraft(null)
            onChange(clampQuantity(parsed, max))
          }}
          onBlur={() => setDraft(null)}
        />
        <button
          type="button"
          aria-label="Increase quantity"
          disabled={isDisabled || value >= max}
          onClick={() => onChange(clampQuantity(value + 1, max))}
        >
          +
        </button>
      </div>
      <p id={hintId} className="hint">
        {isDisabled ? 'Choose an in-stock option to set a quantity.' : `Maximum ${max}`}
      </p>
    </div>
  )
}
