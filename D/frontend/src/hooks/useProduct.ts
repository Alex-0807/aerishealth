import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchProduct } from '../api/productApi'
import type { Product } from '../domain/product'

export type ProductState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; product: Product }

export interface UseProduct {
  state: ProductState
  /** Full reload after a load error (shows the loading state). */
  retry: () => void
  /** Silent background revalidation; keeps current data on screen and on failure. */
  refresh: () => Promise<void>
  /** Apply authoritative stock returned by a mutation without waiting for a refetch. */
  applyStock: (skuId: string, availableQuantity: number) => void
}

export function useProduct(productId: string): UseProduct {
  const [state, setState] = useState<ProductState>({ status: 'loading' })
  // Every load/patch takes a new sequence number; a response is applied only if
  // nothing newer has happened since it was requested (out-of-order protection).
  const seq = useRef(0)

  const load = useCallback(
    async (mode: 'initial' | 'background') => {
      const id = ++seq.current
      if (mode === 'initial') setState({ status: 'loading' })
      try {
        const product = await fetchProduct(productId)
        if (id === seq.current) setState({ status: 'ready', product })
      } catch {
        if (id !== seq.current) return
        // A failed background refresh keeps showing the last good data.
        setState((prev) =>
          mode === 'background' && prev.status === 'ready'
            ? prev
            : { status: 'error', message: 'We couldn’t load this product.' },
        )
      }
    },
    [productId],
  )

  useEffect(() => {
    void load('initial')
  }, [load])

  const retry = useCallback(() => void load('initial'), [load])
  const refresh = useCallback(() => load('background'), [load])

  const applyStock = useCallback((skuId: string, availableQuantity: number) => {
    seq.current++ // a refresh that started before this mutation result is now stale
    setState((prev) =>
      prev.status !== 'ready'
        ? prev
        : {
            status: 'ready',
            product: {
              ...prev.product,
              skus: prev.product.skus.map((s) => (s.id === skuId ? { ...s, availableQuantity } : s)),
            },
          },
    )
  }, [])

  return { state, retry, refresh, applyStock }
}
