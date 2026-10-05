import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchCart } from '../api/cartApi'
import type { Cart } from '../domain/cart'

export type CartState = { status: 'loading' } | { status: 'error' } | { status: 'ready'; cart: Cart }

export interface UseCart {
  state: CartState
  refresh: () => Promise<void>
  setCart: (cart: Cart) => void
}

export function useCart(): UseCart {
  const [state, setState] = useState<CartState>({ status: 'loading' })
  const seq = useRef(0)

  const refresh = useCallback(async () => {
    const id = ++seq.current
    try {
      const cart = await fetchCart()
      if (id === seq.current) setState({ status: 'ready', cart })
    } catch {
      if (id === seq.current) setState((prev) => (prev.status === 'ready' ? prev : { status: 'error' }))
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const setCart = useCallback((cart: Cart) => {
    seq.current++
    setState({ status: 'ready', cart })
  }, [])

  return { state, refresh, setCart }
}
