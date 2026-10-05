export const DEFAULT_TIMEOUT_MS = 10_000

export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown> }
}

/** The server answered with a non-2xx status. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

/** No (usable) response: offline, DNS, connection reset, timeout. The request may or may not have been processed. */
export class NetworkError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options)
    this.name = 'NetworkError'
  }
}

/**
 * "Outcome unknown" failures: the server may or may not have applied the request.
 * These are the ones that must be retried with the SAME idempotency key.
 */
export function isRetryable(error: unknown): boolean {
  return error instanceof NetworkError || (error instanceof ApiError && error.status >= 500)
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false
  const err = (value as { error: unknown }).error
  return typeof err === 'object' && err !== null && 'code' in err && 'message' in err
}

export async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      headers: { Accept: 'application/json', ...init.headers },
      signal: controller.signal,
    })
  } catch (cause) {
    throw new NetworkError(controller.signal.aborted ? 'Request timed out' : 'Network request failed', { cause })
  } finally {
    clearTimeout(timer)
  }

  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    // Non-JSON body (e.g. a proxy's HTML 502 page); handled below.
  }

  if (!response.ok) {
    if (isApiErrorBody(body)) {
      throw new ApiError(response.status, body.error.code, body.error.message, body.error.details ?? {})
    }
    throw new ApiError(response.status, response.status >= 500 ? 'INTERNAL_ERROR' : 'HTTP_ERROR', `Request failed (${response.status})`)
  }
  if (body === null) throw new ApiError(response.status, 'INVALID_RESPONSE', 'Server returned an invalid response')
  return body as T
}
