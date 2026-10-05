import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { deferred, errorResponse, json, mockApi } from '../test/mockApi'
import { ProductPage } from './ProductPage'

async function renderPage() {
  const user = userEvent.setup()
  render(<ProductPage productId="classic-tee" />)
  await screen.findByRole('heading', { name: 'Everyday Organic Tee' })
  return user
}

const group = (label: string) => screen.getByRole('group', { name: new RegExp(`^${label}`) })
const option = (dimension: string, value: string) =>
  within(group(dimension)).getByRole('button', { name: new RegExp(`^${value}\\b`) })
const addButton = () => screen.getByRole('button', { name: /add to cart|adding/i })
const quantityInput = () => screen.getByRole('spinbutton', { name: 'Quantity' })
const availability = () => screen.getByTestId('availability')
// The success live region is always mounted (so it is announced reliably); wait for its text.
const expectStatus = (text: string) =>
  waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(text), { timeout: 2000 })

describe('ProductPage: variant resolution', () => {
  it('selecting Blue + M shows that SKU’s price, stock and image', async () => {
    mockApi()
    const user = await renderPage()

    await user.click(option('Colour', 'Blue'))
    await user.click(option('Size', 'M'))

    expect(option('Colour', 'Blue')).toHaveAttribute('aria-pressed', 'true')
    expect(option('Size', 'M')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('price')).toHaveTextContent('$31.90')
    expect(availability()).toHaveTextContent('In stock: 4 available')
    const image = screen.getByRole('img', { name: 'Everyday Organic Tee in Blue / M' })
    expect(image).toHaveAttribute('src', '/static/images/tee-blue.svg')
    expect(addButton()).toBeEnabled()
  })

  it('switching option immediately replaces price, image and stock (no stale SKU data)', async () => {
    mockApi()
    const user = await renderPage()
    await user.click(option('Colour', 'Blue'))
    await user.click(option('Size', 'M'))

    await user.click(option('Colour', 'Black'))

    expect(screen.getByTestId('price')).toHaveTextContent('$29.90')
    expect(availability()).toHaveTextContent('only 3 left')
    expect(screen.getByRole('img', { name: /Black \/ M/ })).toHaveAttribute('src', '/static/images/tee-black.svg')
  })
})

describe('ProductPage: incomplete, unavailable and out-of-stock are distinct', () => {
  it('asks the user to complete an incomplete selection', async () => {
    mockApi()
    const user = await renderPage()

    expect(availability()).toHaveTextContent('Please select a colour and size.')
    await user.click(option('Colour', 'Blue'))

    expect(availability()).toHaveTextContent('Please select a size.')
    expect(addButton()).toBeDisabled()
    expect(quantityInput()).toBeDisabled()
  })

  it('disables option values that would form a non-existent combination', async () => {
    mockApi()
    const user = await renderPage()

    await user.click(option('Colour', 'Blue'))

    expect(option('Size', 'XL')).toBeDisabled()
    expect(option('Size', 'S')).toBeEnabled() // exists, merely out of stock
    expect(option('Size', 'S')).toHaveAccessibleName('S (out of stock)')
  })

  it('shows "Out of stock" for an existing SKU with zero stock and blocks purchase', async () => {
    mockApi()
    const user = await renderPage()

    await user.click(option('Colour', 'Blue'))
    await user.click(option('Size', 'S'))

    expect(availability()).toHaveTextContent(/^Out of stock$/)
    expect(screen.getByTestId('price')).toHaveTextContent('$29.90')
    expect(addButton()).toBeDisabled()
    expect(quantityInput()).toBeDisabled()
  })

  it('shows "combination unavailable" when refreshed data no longer contains the selected SKU', async () => {
    const api = mockApi()
    const user = await renderPage()
    await user.click(option('Colour', 'Red'))
    await user.click(option('Size', 'XL'))

    // The SKU is discontinued server-side between page load and the click.
    api.state.product.skus = api.state.product.skus.filter((s) => s.id !== 'TEE-RED-XL')
    await user.click(addButton())

    await waitFor(() =>
      expect(availability()).toHaveTextContent('This combination is unavailable. Please choose a different option.'),
    )
    expect(screen.getByRole('alert')).toHaveTextContent('no longer available')
    expect(addButton()).toBeDisabled()
    expect(screen.getByTestId('price')).toBeEmptyDOMElement()
  })
})

describe('ProductPage: quantity', () => {
  it('clamps quantity to the newly selected SKU’s stock', async () => {
    mockApi()
    const user = await renderPage()
    await user.click(option('Colour', 'Black'))
    await user.click(option('Size', 'S')) // stock 5
    await user.clear(quantityInput())
    await user.type(quantityInput(), '5')
    expect(quantityInput()).toHaveValue(5)

    await user.click(option('Size', 'XL')) // stock 2

    expect(quantityInput()).toHaveValue(2)
    expect(screen.getByRole('button', { name: 'Increase quantity' })).toBeDisabled()
  })

  it('never lets the user type more than the available stock', async () => {
    mockApi()
    const user = await renderPage()
    await user.click(option('Colour', 'Blue'))
    await user.click(option('Size', 'L')) // stock 2

    await user.clear(quantityInput())
    await user.type(quantityInput(), '9')

    expect(quantityInput()).toHaveValue(2)
  })
})

describe('ProductPage: add to cart', () => {
  it('rapid clicks trigger exactly one request while the operation is in flight', async () => {
    const api = mockApi()
    const pending = deferred<Response>()
    api.state.postItem = () => pending.promise
    const user = await renderPage()
    await user.click(option('Colour', 'Blue'))
    await user.click(option('Size', 'M'))

    const button = addButton()
    fireEvent.click(button)
    fireEvent.click(button)
    fireEvent.click(button)
    await user.click(button)

    expect(api.posts).toHaveLength(1)
    expect(button).toBeDisabled()
    expect(button).toHaveTextContent('Adding…')
    expect(button).toHaveAttribute('aria-busy', 'true')

    pending.resolve(
      json(201, {
        cart: { items: [], total_quantity: 1, subtotal_cents: 3190, currency: 'AUD' },
        sku: { id: 'TEE-BLU-M', available_quantity: 3 },
      }),
    )

    await expectStatus('Added 1 × Blue / M to your cart.')
    expect(screen.getByTestId('cart-count')).toHaveTextContent('Cart: 1 item')
    expect(api.posts).toHaveLength(1)
  })

  it('reuses the same Idempotency-Key when retrying after a network failure', async () => {
    const api = mockApi()
    let attempt = 0
    api.state.postItem = (call) => {
      attempt++
      if (attempt === 1) throw new TypeError('Failed to fetch') // e.g. connection dropped
      return api.defaultPost(call)
    }
    const user = await renderPage()
    await user.click(option('Colour', 'Blue'))
    await user.click(option('Size', 'M'))

    await user.click(addButton())

    await expectStatus('Added 1 × Blue / M')
    expect(api.posts).toHaveLength(2)
    expect(api.posts[0]?.idempotencyKey).toBeTruthy()
    expect(api.posts[1]?.idempotencyKey).toBe(api.posts[0]?.idempotencyKey)

    // A new logical operation gets a new key.
    await user.click(addButton())
    await waitFor(() => expect(api.posts).toHaveLength(3))
    expect(api.posts[2]?.idempotencyKey).not.toBe(api.posts[0]?.idempotencyKey)
  })

  it('offers a manual retry that keeps the original key when automatic retries are exhausted', async () => {
    const api = mockApi()
    let failing = true
    api.state.postItem = (call) => {
      if (failing) return errorResponse(503, 'SERVICE_UNAVAILABLE', 'busy')
      return api.defaultPost(call)
    }
    const user = await renderPage()
    await user.click(option('Colour', 'Blue'))
    await user.click(option('Size', 'M'))
    await user.click(addButton())

    const alert = await screen.findByRole('alert', {}, { timeout: 2000 })
    expect(alert).toHaveTextContent('Something went wrong on our side')
    expect(addButton()).toBeEnabled() // page remains usable

    failing = false
    await user.click(within(alert).getByRole('button', { name: 'Try again' }))

    await expectStatus('Added 1 × Blue / M')
    const keys = new Set(api.posts.map((p) => p.idempotencyKey))
    expect(api.posts).toHaveLength(3)
    expect(keys.size).toBe(1)
  })

  it('on 409 shows an error, refetches product + cart, and updates stock without a reload', async () => {
    const api = mockApi()
    const user = await renderPage()
    await user.click(option('Colour', 'Black'))
    await user.click(option('Size', 'M')) // UI believes stock = 3
    await user.click(screen.getByRole('button', { name: 'Increase quantity' }))
    await user.click(screen.getByRole('button', { name: 'Increase quantity' }))
    expect(quantityInput()).toHaveValue(3)

    // Another customer buys two units after our page loaded.
    api.state.product.skus.find((s) => s.id === 'TEE-BLK-M')!.available_quantity = 1
    const gets = api.productGets.count
    await user.click(addButton())

    expect(await screen.findByRole('alert')).toHaveTextContent('Only 1 of Black / M left')
    await waitFor(() => expect(availability()).toHaveTextContent('only 1 left'))
    expect(api.productGets.count).toBeGreaterThan(gets)
    expect(quantityInput()).toHaveValue(1)
    expect(addButton()).toBeEnabled()

    // ...and the user can complete the purchase with the corrected quantity.
    await user.click(addButton())
    await expectStatus('Added 1 × Black / M')
    await waitFor(() => expect(availability()).toHaveTextContent('Out of stock'))
  })

  it('shows a validation error from the server', async () => {
    const api = mockApi()
    api.state.postItem = () =>
      errorResponse(422, 'INVALID_QUANTITY', 'Quantity must be a whole number between 1 and 99', { min: 1, max: 99 })
    const user = await renderPage()
    await user.click(option('Colour', 'Blue'))
    await user.click(option('Size', 'M'))

    await user.click(addButton())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('That quantity isn’t valid')
    expect(within(alert).queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(api.posts).toHaveLength(1) // 4xx is definitive: no automatic retry
  })
})

describe('ProductPage: loading', () => {
  it('shows loading, then a load error with a working retry', async () => {
    const api = mockApi()
    api.state.getProduct = () => errorResponse(500, 'INTERNAL_ERROR', 'boom')
    const user = userEvent.setup()
    render(<ProductPage productId="classic-tee" />)

    expect(screen.getByRole('status')).toHaveTextContent('Loading product…')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('We couldn’t load this product.')

    api.state.getProduct = null
    await user.click(within(alert).getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { name: 'Everyday Organic Tee' })).toBeInTheDocument()
  })
})
