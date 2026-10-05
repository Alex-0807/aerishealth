# Product Detail Page — FastAPI + React

A small but production-minded Product Detail Page (PDP): one product with Colour × Size variants, a FastAPI + SQLite backend that reserves stock safely under concurrency with idempotent add-to-cart, and a React + TypeScript frontend that resolves variants, handles every purchase state explicitly and recovers from stale data and network failures without a page reload.

- [Setup](#setup)
- [Architecture](#architecture)
- [API contract](#api-contract)
- [Concurrency: preventing overselling](#concurrency-preventing-overselling)
- [Idempotency](#idempotency)
- [Network and stale-data strategy](#network-and-stale-data-strategy)
- [Frontend state model](#frontend-state-model)
- [Accessibility](#accessibility)
- [Trade-offs and scope](#trade-offs-and-scope)

---

## Setup

Requirements: **Python 3.11+**, **Node 20+** (developed with Python 3.12 and Node 24).

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn --factory pdp.main:create_app --reload --port 8000
```

The SQLite database (`backend/data/pdp.db`) is created and seeded automatically on first start, so the app is usable immediately.

- API docs (supplementary): <http://127.0.0.1:8000/docs>
- Reset to the seed data: `python -m pdp.seed --reset`
- Use a different DB file: `PDP_DB_PATH=/tmp/other.db uvicorn --factory pdp.main:create_app`

### Frontend

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

Vite proxies `/api` and `/static` to `http://127.0.0.1:8000` (override with `PDP_BACKEND_URL`), so the browser talks to a single origin and no CORS setup is needed.

### Tests

```bash
cd backend && .venv/bin/python -m pytest        # 34 tests, incl. real-HTTP race tests
cd frontend && npm test                         # 25 tests (Vitest + React Testing Library)
cd frontend && npm run typecheck && npm run build
```

### Exercising failure scenarios manually

| Scenario | How |
|---|---|
| Stock changes after the page loaded | Select Black / L (1 left), then run `sqlite3 backend/data/pdp.db "UPDATE skus SET quantity=0 WHERE id='TEE-BLK-L'"` and click **Add to cart** → 409, the UI refreshes and shows "Out of stock". |
| Latency | `PDP_CHAOS_LATENCY_MS=1500 uvicorn --factory pdp.main:create_app` (or DevTools throttling) |
| Lost responses after a successful write | `PDP_CHAOS_FAIL_RATE=0.5 uvicorn --factory pdp.main:create_app` — the POST commits, then the response is replaced by a 503. The frontend retries with the same key and the server replays the stored result, so the item is not added twice. |
| API down | Stop the backend: the page shows a load error with **Try again**; add-to-cart shows a retryable error. |

---

## Architecture

```
backend/
  pdp/
    main.py          create_app(): routes, dependency-injected per-request SQLite connection
    db.py            schema, connection settings, write_transaction() (BEGIN IMMEDIATE … COMMIT/ROLLBACK)
    seed.py          seed data (+ `python -m pdp.seed --reset`)
    products.py      read model for GET /api/products/{id}
    cart.py          add_item(): idempotency + atomic reservation + cart upsert in one transaction; get_cart()
    idempotency.py   key validation, request fingerprint, load/save of stored responses
    errors.py        ApiError, error codes, handlers that produce {"error": {...}} for every failure
    schemas.py       Pydantic request validation and response models (drive /docs)
    chaos.py         opt-in latency / lost-response injection for manual testing
  tests/             API, idempotency and real-HTTP concurrency tests

frontend/src/
  api/          http.ts (fetch wrapper: timeouts, ApiError vs NetworkError), productApi.ts, cartApi.ts (DTO → domain mapping)
  domain/       product.ts, cart.ts (types), resolveVariant.ts, quantity.ts (pure functions, unit tested)
  hooks/        useProduct, useCart (loading + background revalidation), useAddToCart (submission state machine + idempotency keys)
  components/   ProductGallery, VariantSelector, AvailabilityMessage, QuantitySelector, AddToCartButton, AddToCartFeedback, CartCount
  pages/        ProductPage (load states, layout), ProductDetails (selection state, derivations, wiring)
```

### Key decisions

**Backend**

- **Raw `sqlite3`, no ORM.** The interesting part of this task is the exact SQL and transaction boundaries. With raw SQL they are visible and easy to review. An ORM would hide them for little benefit at this size.
- **Option dimensions are data.** `product_options` / `product_option_values` / `sku_option_values` rather than `colour` and `size` columns, so the API returns `options: [{name, label, values}]` and the frontend has no hard-coded dimensions.
- **Money is integer cents**, so there are no floating-point rounding issues. Currency is per product.
- **The cart stores no price.** `GET /api/cart` joins `skus` for the current price. The POST body accepts only `sku_id` and `quantity`, and unknown fields like `price_cents` are ignored. So the client can't influence price or stock.
- **Adding to cart reserves stock.** This is what the spec asks for ("prevent overselling" at add time). A real shop would add reservation expiry (see trade-offs).
- **Defence in depth:** `CHECK (quantity >= 0)` on `skus` means even a future buggy unconditional decrement fails loudly instead of overselling.

**Frontend**

- **Only user choices are state** (`selectedOptions`, `quantity`). The selected SKU, price, image, stock message and max quantity are all *derived* from `product` + `selectedOptions` on every render:

  ```ts
  const variant = useMemo(() => resolveVariant(product, selected), [product, selected])
  ```

  So refreshed product data or a changed option can never leave stale SKU information on screen. No effect has to "sync" anything.
- **Variant logic is pure and separately tested** (`domain/resolveVariant.ts`). It returns a discriminated union: `incomplete | unavailable | out_of_stock | available`.
- **Network concerns live in hooks**, so components stay presentational.

---

## API contract

All errors use one shape:

```json
{ "error": { "code": "INSUFFICIENT_STOCK", "message": "Not enough stock", "details": { "requested": 2, "available": 1 } } }
```

| Code | Status | When |
|---|---|---|
| `INVALID_QUANTITY` | 422 | quantity missing, not an integer (`"2"`, `1.5`, `true` are rejected), < 1 or > 99 |
| `VALIDATION_ERROR` | 422 | other body problems (e.g. missing `sku_id`); `details.fields` lists them |
| `MISSING_IDEMPOTENCY_KEY` / `INVALID_IDEMPOTENCY_KEY` | 400 | header absent / not 1–255 chars of `[A-Za-z0-9._:-]` |
| `IDEMPOTENCY_KEY_REUSED` | 422 | same key sent with a different body |
| `PRODUCT_NOT_FOUND` / `SKU_NOT_FOUND` / `NOT_FOUND` | 404 | unknown product / SKU / route |
| `INSUFFICIENT_STOCK` | 409 | not enough stock at the moment of the atomic update |
| `SERVICE_UNAVAILABLE` | 503 | database write lock not acquired within the busy timeout (with `Retry-After: 1`); safe to retry with the same key |
| `INTERNAL_ERROR` | 500 | anything unexpected; internals are not leaked, the transaction is rolled back |

### `GET /api/products/{id}`

`200 OK` · `404 PRODUCT_NOT_FOUND`

```http
GET /api/products/classic-tee
```

```json
{
  "id": "classic-tee",
  "name": "Everyday Organic Tee",
  "description": "A mid-weight organic cotton tee with a relaxed fit. …",
  "currency": "AUD",
  "image_url": "/static/images/tee-default.svg",
  "options": [
    { "name": "colour", "label": "Colour", "values": ["Black", "Blue", "Red"] },
    { "name": "size",   "label": "Size",   "values": ["S", "M", "L", "XL"] }
  ],
  "skus": [
    {
      "id": "TEE-BLU-M",
      "product_id": "classic-tee",
      "price_cents": 3190,
      "available_quantity": 4,
      "image_url": "/static/images/tee-blue.svg",
      "options": { "colour": "Blue", "size": "M" }
    }
  ]
}
```

Seed data: 10 SKUs. **Blue/XL** and **Red/S** do not exist, **Blue/S** exists with 0 stock, **Black/L** has exactly 1 unit, and prices (27.90–32.90) and images (per colour) vary.

### `POST /api/cart/items`

`201 Created` · `400` · `404 SKU_NOT_FOUND` · `409 INSUFFICIENT_STOCK` · `422` · `500` · `503`

```http
POST /api/cart/items
Content-Type: application/json
Idempotency-Key: 6f1c0d7e-1f7a-4a8e-9d55-0c8e3b4b2a10

{ "sku_id": "TEE-BLU-M", "quantity": 2 }
```

```json
HTTP/1.1 201 Created

{
  "cart": {
    "items": [
      {
        "sku_id": "TEE-BLU-M", "product_id": "classic-tee", "product_name": "Everyday Organic Tee",
        "options": { "colour": "Blue", "size": "M" }, "image_url": "/static/images/tee-blue.svg",
        "unit_price_cents": 3190, "quantity": 2, "line_total_cents": 6380
      }
    ],
    "total_quantity": 2,
    "subtotal_cents": 6380,
    "currency": "AUD"
  },
  "sku": { "id": "TEE-BLU-M", "available_quantity": 2 }
}
```

The response carries the updated cart and the SKU's new authoritative stock, so the UI can update both without another round trip.

Replaying the same key returns the **identical** stored status and body plus the header `Idempotent-Replayed: true`.

```json
HTTP/1.1 409 Conflict

{ "error": { "code": "INSUFFICIENT_STOCK", "message": "Not enough stock",
             "details": { "sku_id": "TEE-BLU-M", "requested": 5, "available": 2 } } }
```

```json
HTTP/1.1 422 Unprocessable Content

{ "error": { "code": "INVALID_QUANTITY", "message": "Quantity must be a whole number between 1 and 99",
             "details": { "min": 1, "max": 99, "received": 0 } } }
```

### `GET /api/cart`

`200 OK`

```json
{
  "items": [ { "sku_id": "TEE-BLU-M", "quantity": 2, "unit_price_cents": 3190, "line_total_cents": 6380, "…": "…" } ],
  "total_quantity": 2,
  "subtotal_cents": 6380,
  "currency": "AUD"
}
```

`total_quantity` is the total item count (sum of line quantities), shown as the cart badge.

---

## Concurrency: preventing overselling

### The race

Two customers both see "1 left" and click **Add to cart** at the same moment. A naive implementation:

```python
stock = SELECT quantity FROM skus WHERE id = ?      # both read 1
if stock >= qty:                                    # both pass
    UPDATE skus SET quantity = ? WHERE id = ?       # both write 0
    INSERT INTO cart_items …                        # both get the item
```

Both requests read before either writes, so both pass the check. That's two units sold and stock at 0, a classic *lost update*. The check and the write are separate steps, and other transactions can run in between.

This isn't hypothetical. While building this I swapped that naive version into the real server and ran the race test from `tests/test_concurrency.py`. The result was `[201, 201]`, stock 0 and **2 units in carts**.

### The fix: one atomic conditional update

```sql
UPDATE skus
SET quantity = quantity - :qty
WHERE id = :sku_id
  AND quantity >= :qty;
```

The check (`quantity >= :qty`) and the decrement are one statement, which the database executes atomically against the current row. Afterwards we look at `cursor.rowcount`:

- `1` means the stock was reserved, so we continue and add the item to the cart.
- `0` means there wasn't enough stock at that moment, so we return `409 INSUFFICIENT_STOCK` with the current `available` count.

**Two callers, final unit:** request A's UPDATE runs first and changes the row to 0 (rowcount 1). Request B's UPDATE then evaluates `0 >= 1`, which is false, so rowcount is 0 and B gets a 409. Stock ends at 0 and exactly one cart line exists. Whichever order they arrive in, exactly one wins.

### SQLite specifics and transaction decisions

- **SQLite allows only one writer at a time** (database-level lock), and that's what serialises the writes here. I start write transactions with **`BEGIN IMMEDIATE`**, which takes the write lock up front. With the default `BEGIN DEFERRED`, two transactions could both read and then race to upgrade to a write lock, and one would fail with `SQLITE_BUSY`. With `IMMEDIATE`, the second writer waits (up to `busy_timeout` = 10 s) and then sees the first one's committed result.
- **Is the conditional UPDATE redundant, then?** On SQLite, `BEGIN IMMEDIATE` alone already serialises writers. I still use the conditional UPDATE, because it's correct *by itself*: it doesn't depend on SQLite's coarse locking. It would stay correct on PostgreSQL/MySQL under the default READ COMMITTED isolation, where the naive SELECT-then-UPDATE really does oversell. The two together give a correct statement and a predictable, non-erroring transaction.
- **WAL mode** (`PRAGMA journal_mode=WAL`) lets `GET` requests read while a write is in progress.
- **One connection per request.** FastAPI runs the sync endpoints in a threadpool, so concurrent requests really do hit SQLite from different threads and connections. That's the setup the race tests exercise.
- **Limits:** SQLite write throughput is bounded by the single writer lock. Under heavy contention requests queue, and past the busy timeout they get `503 SERVICE_UNAVAILABLE` with `Retry-After`, which the client may safely retry thanks to idempotency. For real traffic I'd move to PostgreSQL. The same SQL works there, and its row-level locking lets different SKUs proceed in parallel.

### How it is tested

`tests/test_concurrency.py` starts a **real uvicorn server** on a free port and fires simultaneous HTTP requests from separate threads, released together by a `threading.Barrier`. (`TestClient` processes requests one at a time in-process, so it would hide the race.)

- Two buyers, final unit: exactly one `201` and one `409 INSUFFICIENT_STOCK` with `available: 0`, final stock 0, cart quantity 1.
- The same race repeated 25 times, because a race test that passes once might have passed by luck.
- 12 buyers for 3 units: exactly 3 succeed and 9 get 409.
- 6 concurrent requests with the **same** key: one mutation and five identical replays.

---

## Idempotency

### Why

A client can't tell "the request never arrived" apart from "the request succeeded but the response was lost" (timeout, dropped connection, proxy 502). Retrying is the right reaction, but a blind retry of a non-idempotent POST would add the item twice and reserve stock twice.

### How it works

Every `POST /api/cart/items` must carry an `Idempotency-Key`. In **one** `BEGIN IMMEDIATE` transaction the server:

1. Looks up `(cart_id, key)` in `idempotency_keys`.
   - Found with the same request fingerprint (SHA-256 of `{sku_id, quantity}`): it returns the stored status code and body, with `Idempotent-Replayed: true`. Nothing is mutated.
   - Found with a different fingerprint: it returns `422 IDEMPOTENCY_KEY_REUSED`, because a key may not be recycled for a different request.
2. Otherwise it runs the atomic stock reservation and the cart upsert.
3. It stores the response (status + JSON body) under the key, then **COMMITs**.

Because all of this is one transaction:

- **No partial state.** If anything fails midway (tested by making the save step raise *after* the stock decrement), the whole transaction rolls back: stock, cart and key. A retry with the same key then runs cleanly.
- **No duplicate on concurrent retries.** The lookup happens *inside* the write lock, so a second request with the same key waits for the first to commit and then finds the stored response. The `(cart_id, key)` primary key is a further backstop.

**What is stored.** Processed outcomes are stored: `201` and `409 INSUFFICIENT_STOCK`. Retrying that same key after a restock still returns 409, because the key identifies that one attempt and its answer doesn't change (the same semantics as Stripe). Requests that never reached the business logic (validation errors, unknown SKU) and `5xx` failures (rolled back) are not stored, so they can be retried.

### Why the same logical retry must reuse the key

The key represents *one user intention* ("add 2 × Blue / M"), not one HTTP attempt. If the client made a new key for every retry, the server would treat each retry as a new purchase and the protection would be gone. So in the frontend (`hooks/useAddToCart.ts`):

- A **new key** is created when the user starts a new add-to-cart operation.
- The **same key** is reused for the automatic retry (one retry after 400 ms for network errors and 5xx) and for the manual **Try again** after an "outcome unknown" failure. Clicking **Add to cart** again with the same SKU and quantity after such a failure also counts as a retry.
- The key is **discarded** once the server gives a definitive answer (2xx or 4xx). Adding the same item again after a success is a new operation with a new key.

Keys are scoped to the cart and kept indefinitely in this assessment. Production would expire them (e.g. after 24 h).

---

## Network and stale-data strategy

The initial `GET /api/products/{id}` is treated as a **snapshot, not the truth**. The server is the only authority on stock and price.

| Situation | Behaviour |
|---|---|
| `409 INSUFFICIENT_STOCK` (someone bought it first) | `role="alert"` message using the server's `available` count ("Only 1 of Black / M left …" / "… has just sold out"). The product and cart are refetched in the background. Because SKU, stock and max quantity are *derived*, the new stock immediately updates the status text and **clamps the quantity** (3 → 1). The page stays interactive, so the user can buy the corrected quantity without a reload. |
| `404 SKU_NOT_FOUND` (SKU removed) | Error message plus a refetch. The selection then resolves to "This combination is unavailable". |
| Network error / timeout / `5xx` | The outcome is unknown, so the client retries automatically once with the **same** key. If that also fails, a retryable alert with **Try again** (same key) appears, and product and cart are refetched to show what actually happened. |
| `422` validation | Error shown, no retry (definitive). |
| Successful add | The cart and SKU stock from the response are applied immediately, then the product is revalidated in the background (other SKUs may have changed too). |
| Product load failure | A full-page error with **Try again**. A failed *background* refresh keeps the last good data on screen. |

Supporting details:

- **Out-of-order responses.** `useProduct` and `useCart` tag each request with a sequence number and ignore responses older than the latest request or local patch, so a slow, older refresh can't overwrite newer stock.
- **Timeouts.** Every request has an `AbortController` timeout (10 s) and is classified as a `NetworkError`.
- **No HTTP caching** of product or cart (`cache: 'no-store'`).

---

## Frontend state model

```ts
// domain/resolveVariant.ts
type VariantResolution =
  | { status: 'incomplete'; missing: OptionDimension[] }   // "Please select a size."
  | { status: 'unavailable' }                              // "This combination is unavailable…"
  | { status: 'out_of_stock'; sku: Sku }                   // "Out of stock"
  | { status: 'available'; sku: Sku }                      // "In stock: 4 available"

// hooks/useProduct.ts
type ProductState = { status: 'loading' } | { status: 'error'; message } | { status: 'ready'; product }

// hooks/useAddToCart.ts
type AddToCartState =
  | { status: 'idle' }
  | { status: 'submitting'; request }
  | { status: 'success'; request; result }
  | { status: 'error'; request; failure: AddToCartFailure; retryable: boolean }

type AddToCartFailure =
  | { kind: 'insufficient_stock'; requested; available } | { kind: 'invalid_quantity'; message }
  | { kind: 'sku_not_found' } | { kind: 'validation'; message } | { kind: 'network' } | { kind: 'server' }
```

**Option disabling.** A value is *impossible* (disabled) if no SKU has it combined with the other dimensions' current selections. It is *sold out* (enabled, dashed border, accessible name "S (out of stock)") if SKUs exist but all have 0 stock. The user can still select it and see "Out of stock", which keeps "doesn't exist" and "exists but empty" distinct. Clicking a selected value again deselects it, so a user who has picked XL can clear it to pick Blue.

**Quantity.** `quantity` is state, and `effectiveQuantity = clamp(quantity, 1, min(stock, 99))` is derived. Changing the option also *commits* the clamp (5 on a 5-stock SKU becomes 2 after switching to a 2-stock SKU, and stays 2). The derived clamp also covers stock dropping after a refresh. The control is disabled unless an in-stock SKU is selected.

**Duplicate clicks.** A `useRef` in-flight guard flips *synchronously*, so a second click in the same frame is rejected before React re-renders. The button is also `disabled` and `aria-busy` with an "Adding…" label while submitting. The test fires four rapid clicks and asserts a single POST.

**Images.** Shows the selected SKU's image. With a partial selection, it shows the variant image only if every matching SKU shares it (e.g. colour chosen, size not), otherwise the neutral product image. `<img key={url}>` makes sure the previous variant's image never lingers.

---

## Accessibility

- Option groups use `<fieldset>`/`<legend>` (the legend shows the current choice, e.g. "Colour: Blue"). Values are native `<button>`s with `aria-pressed`, so they're keyboard operable with Tab, Enter and Space.
- Impossible values use the native `disabled` attribute and drop out of the tab order. Sold-out values say so in their accessible name.
- The quantity input has a `<label>`, `min`/`max` and a hint via `aria-describedby`. The stepper buttons have labels ("Increase quantity").
- Availability text sits in an `aria-live="polite"` region, so changes are announced.
- Add-to-cart success uses an always-mounted `role="status"` region. Errors use `role="alert"`. Page loading is `role="status"` and a load failure is `role="alert"`.
- There's a high-contrast `:focus-visible` ring, ≥44 px touch targets, and `prefers-reduced-motion` support for the spinner.
- The layout is responsive: one column at 375 px, two columns from 768 px, checked at 375 px and 1280 px with no horizontal scrolling.

---

## Trade-offs and scope

- **One anonymous cart** (`cart_id = "default"`), because auth is out of scope. Every query is already parameterised by `cart_id`, so a cookie-based cart id is a small change.
- **Reservations never expire.** Stock is decremented at add-to-cart, as the task requires. A real system would hold reservations with a TTL, release them on cart removal or abandonment, and convert them at checkout.
- **Idempotency records never expire.** Production would add a `created_at` TTL sweep (the column already exists).
- **SQLite** serialises all writes. That's fine here and documented above. PostgreSQL would be the next step, with no change to the reservation SQL.
- **No cart page or cart editing** (no remove or change-quantity endpoints), since the task didn't ask for them.
- **Unavailable combinations are prevented, not just reported.** Disabling impossible values means "combination unavailable" mostly appears when server data changes under the user, e.g. a SKU is removed. It is still a first-class state with its own message and test.
- **No schema migrations tool.** `CREATE TABLE IF NOT EXISTS` plus `--reset` is enough for an assessment.
- **No runtime response validation** (e.g. zod) on the frontend. The API layer maps DTOs to domain types in one place. Schema validation would be the next hardening step.
- **No revalidation on window focus or polling.** Stock is revalidated after every add-to-cart outcome. Focus revalidation would be a small, sensible addition.
- **Chaos middleware** is opt-in via environment variables, purely for demonstrating the recovery paths.
