import { useCallback, useEffect, useRef, useState } from 'react'
import { addCartItem, newIdempotencyKey } from '../api/cartApi'
import { ApiError, isRetryable } from '../api/http'
import type { AddToCartResult } from '../domain/cart'

export interface AddToCartRequest {
  skuId: string
  quantity: number
  /** Human description used in feedback, e.g. "Blue / M". */
  label: string
}

export type AddToCartFailure =
  | { kind: 'insufficient_stock'; requested: number | null; available: number | null }
  | { kind: 'invalid_quantity'; message: string }
  | { kind: 'sku_not_found' }
  | { kind: 'validation'; message: string }
  | { kind: 'network' }
  | { kind: 'server' }

export type AddToCartState =
  | { status: 'idle' }
  | { status: 'submitting'; request: AddToCartRequest }
  | { status: 'success'; request: AddToCartRequest; result: AddToCartResult }
  | { status: 'error'; request: AddToCartRequest; failure: AddToCartFailure; retryable: boolean }

interface PendingOperation {
  request: AddToCartRequest
  idempotencyKey: string
}

export interface UseAddToCartOptions {
  onSuccess?: (result: AddToCartResult) => void
  onFailure?: (failure: AddToCartFailure) => void
  /** Automatic retries for "outcome unknown" failures, reusing the same key. */
  autoRetries?: number
  retryDelayMs?: number
}

const sameItem = (a: AddToCartRequest, b: AddToCartRequest) => a.skuId === b.skuId && a.quantity === b.quantity

const numberOrNull = (v: unknown) => (typeof v === 'number' ? v : null)

export function toFailure(error: unknown): AddToCartFailure {
  if (error instanceof ApiError) {
    switch (error.code) {
      case 'INSUFFICIENT_STOCK':
        return {
          kind: 'insufficient_stock',
          requested: numberOrNull(error.details.requested),
          available: numberOrNull(error.details.available),
        }
      case 'INVALID_QUANTITY':
        return { kind: 'invalid_quantity', message: error.message }
      case 'SKU_NOT_FOUND':
        return { kind: 'sku_not_found' }
    }
    if (error.status < 500) return { kind: 'validation', message: error.message }
    return { kind: 'server' }
  }
  return { kind: 'network' }
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

/**
 * Add-to-cart state machine with idempotent retries.
 *
 * One idempotency key = one logical "add these N of SKU X" operation:
 * - a new key is created when the user starts a new operation
 * - the key is REUSED for automatic retries and for a manual "Try again"
 *   after an outcome-unknown failure (network error / 5xx), because the first
 *   attempt may have been applied and only the response was lost
 * - the key is discarded once the server gives a definitive answer (2xx/4xx)
 */
export function useAddToCart({
  onSuccess,
  onFailure,
  autoRetries = 1,
  retryDelayMs = 400,
}: UseAddToCartOptions = {}) {
  const [state, setState] = useState<AddToCartState>({ status: 'idle' })
  // Refs, not state: the guard must flip synchronously, before React re-renders,
  // so that a second click in the same frame is rejected.
  const inFlight = useRef(false)
  const pending = useRef<PendingOperation | null>(null)

  const callbacks = useRef({ onSuccess, onFailure })
  useEffect(() => {
    callbacks.current = { onSuccess, onFailure }
  })

  // Stop automatic retries once the component is gone.
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const submit = useCallback(
    async (request: AddToCartRequest) => {
      if (inFlight.current) return
      inFlight.current = true

      const previous = pending.current
      const operation =
        previous && sameItem(previous.request, request) ? previous : { request, idempotencyKey: newIdempotencyKey() }
      pending.current = operation
      setState({ status: 'submitting', request })

      try {
        let attempt = 0
        for (;;) {
          try {
            const result = await addCartItem(request, operation.idempotencyKey)
            pending.current = null
            setState({ status: 'success', request, result })
            callbacks.current.onSuccess?.(result)
            return
          } catch (error) {
            const retryable = isRetryable(error)
            if (retryable && attempt < autoRetries) {
              attempt++
              await wait(retryDelayMs * attempt)
              if (!mounted.current) return
              continue
            }
            if (!retryable) pending.current = null // definitive answer: next attempt is a new operation
            const failure = toFailure(error)
            setState({ status: 'error', request, failure, retryable })
            callbacks.current.onFailure?.(failure)
            return
          }
        }
      } finally {
        inFlight.current = false
      }
    },
    [autoRetries, retryDelayMs],
  )

  /** Retry the last outcome-unknown operation with its original key. */
  const retry = useCallback(() => {
    if (pending.current) void submit(pending.current.request)
  }, [submit])

  const reset = useCallback(() => {
    if (!inFlight.current) setState({ status: 'idle' })
  }, [])

  return { state, submit, retry, reset }
}
