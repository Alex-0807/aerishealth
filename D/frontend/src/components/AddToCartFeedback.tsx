import type { AddToCartFailure, AddToCartState } from '../hooks/useAddToCart'

function failureMessage(failure: AddToCartFailure, label: string): string {
  switch (failure.kind) {
    case 'insufficient_stock':
      return failure.available === 0
        ? `Sorry, ${label} has just sold out. Stock has been updated.`
        : `Only ${failure.available ?? 'a few'} of ${label} left — we’ve updated the available quantity. Please try again.`
    case 'invalid_quantity':
      return `That quantity isn’t valid: ${failure.message}`
    case 'sku_not_found':
      return 'This option is no longer available. The product details have been refreshed.'
    case 'validation':
      return `We couldn’t add this item: ${failure.message}`
    case 'network':
      return 'We couldn’t reach the server, so we can’t confirm the item was added. Check your connection and try again.'
    case 'server':
      return 'Something went wrong on our side. Please try again.'
  }
}

interface Props {
  state: AddToCartState
  onRetry: () => void
}

export function AddToCartFeedback({ state, onRetry }: Props) {
  return (
    <div className="feedback">
      {/* Always mounted so assistive tech reliably announces content changes. */}
      <p role="status" className="feedback__success">
        {state.status === 'success'
          ? `Added ${state.request.quantity} × ${state.request.label} to your cart.`
          : ''}
      </p>
      {state.status === 'error' ? (
        <div role="alert" className="feedback__error">
          <p>{failureMessage(state.failure, state.request.label)}</p>
          {state.retryable ? (
            <button type="button" className="link-button" onClick={onRetry}>
              Try again
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
