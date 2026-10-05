import type { CartState } from '../hooks/useCart'

export function CartCount({ state }: { state: CartState }) {
  const text =
    state.status === 'ready'
      ? `${state.cart.totalQuantity} ${state.cart.totalQuantity === 1 ? 'item' : 'items'}`
      : state.status === 'loading'
        ? '…'
        : 'unavailable'
  return (
    <p className="cart-count" data-testid="cart-count">
      <span aria-hidden="true">🛒 </span>Cart: {text}
    </p>
  )
}
