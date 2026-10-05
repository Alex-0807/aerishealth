interface Props {
  disabled: boolean
  submitting: boolean
  onClick: () => void
}

export function AddToCartButton({ disabled, submitting, onClick }: Props) {
  return (
    <button
      type="button"
      className="add-to-cart"
      disabled={disabled || submitting}
      aria-busy={submitting}
      onClick={onClick}
    >
      {submitting ? (
        <>
          <span className="spinner" aria-hidden="true" /> Adding…
        </>
      ) : (
        'Add to cart'
      )}
    </button>
  )
}
