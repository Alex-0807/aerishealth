import { vi } from 'vitest'
import type { CartDto } from '../api/cartApi'
import type { ProductDto } from '../api/productApi'
import { emptyCartDto, productDto } from './fixtures'

export const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

export const errorResponse = (status: number, code: string, message: string, details: Record<string, unknown> = {}) =>
  json(status, { error: { code, message, details } })

export interface PostCall {
  body: { sku_id: string; quantity: number }
  idempotencyKey: string | null
}

type Handler = (call: PostCall) => Response | Promise<Response>

/**
 * A tiny in-memory fake of the backend behind a stubbed global fetch.
 * Tests can mutate `product`/`cart` (e.g. to simulate another customer)
 * or override individual handlers.
 */
export function mockApi() {
  const state = {
    product: productDto() as ProductDto,
    cart: emptyCartDto() as CartDto,
    getProduct: null as null | (() => Response | Promise<Response>),
    postItem: null as null | Handler,
  }

  const defaultPost: Handler = ({ body }) => {
    const sku = state.product.skus.find((s) => s.id === body.sku_id)
    if (!sku) return errorResponse(404, 'SKU_NOT_FOUND', 'SKU not found', { sku_id: body.sku_id })
    if (sku.available_quantity < body.quantity) {
      return errorResponse(409, 'INSUFFICIENT_STOCK', 'Not enough stock', {
        requested: body.quantity,
        available: sku.available_quantity,
      })
    }
    sku.available_quantity -= body.quantity
    state.cart = {
      ...state.cart,
      total_quantity: state.cart.total_quantity + body.quantity,
    }
    return json(201, { cart: state.cart, sku: { id: sku.id, available_quantity: sku.available_quantity } })
  }

  const posts: PostCall[] = []
  const productGets = { count: 0 }

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    const method = init?.method ?? 'GET'
    if (method === 'GET' && url.startsWith('/api/products/')) {
      productGets.count++
      if (state.getProduct) return state.getProduct()
      return json(200, structuredClone(state.product))
    }
    if (method === 'GET' && url === '/api/cart') return json(200, structuredClone(state.cart))
    if (method === 'POST' && url === '/api/cart/items') {
      const headers = new Headers(init?.headers)
      const call: PostCall = {
        body: JSON.parse(String(init?.body)) as PostCall['body'],
        idempotencyKey: headers.get('Idempotency-Key'),
      }
      posts.push(call)
      return (state.postItem ?? defaultPost)(call)
    }
    return errorResponse(404, 'NOT_FOUND', `Unhandled ${method} ${url}`)
  })

  vi.stubGlobal('fetch', fetchMock)
  return { state, posts, productGets, fetchMock, defaultPost }
}

export function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}
