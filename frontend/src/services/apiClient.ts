/**
 * Minimal typed HTTP client for the GeneVerify backend.
 *
 * All future feature services (identity, verification, reports...) build on
 * top of this client so error handling, base URL resolution, auth headers and
 * typing stay consistent across the app.
 */

import { clearAccessToken, getAccessToken } from './tokenStorage'

/**
 * Backend base URL (Step 11: deployment).
 *
 * Development falls back to the local uvicorn instance, so `npm run dev` works
 * before any `.env.local` exists. A **production build never embeds a localhost
 * origin**: `VITE_API_BASE_URL` is read at build time and, if it was not
 * supplied, the build falls back to the same-origin `/api/v1` path so a
 * reverse-proxy deployment works without configuration. `VITE_*` may only ever
 * contain public information — the JWT secret, database credentials and the
 * Qwen API key stay on the backend and are never visible to the browser.
 */
const DEV_API_BASE_URL = 'http://localhost:8000/api/v1'
const SAME_ORIGIN_API_BASE_URL = '/api/v1'

function resolveApiBaseUrl(): string {
  const configured: string = import.meta.env.VITE_API_BASE_URL || ''
  const trimmed = configured.trim().replace(/\/+$/, '')
  if (trimmed) return trimmed
  // `import.meta.env.PROD` is a build-time constant, replaced by Vite.
  return import.meta.env.PROD ? SAME_ORIGIN_API_BASE_URL : DEV_API_BASE_URL
}

export const API_BASE_URL: string = resolveApiBaseUrl()

/** Error thrown for any failed API call, with the HTTP status when known. */
export class ApiError extends Error {
  readonly status: number | null

  constructor(message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function extractErrorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (typeof body === 'object' && body !== null && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'string' && detail.length > 0) {
        return detail
      }
    }
  } catch {
    // Non-JSON error body; fall through to the generic message.
  }
  return `Request failed with status ${response.status}.`
}

/**
 * Optional callback invoked whenever the API answers 401. The auth context
 * registers a handler here to clear state and redirect to the login page.
 * Kept as a callback (not a direct import) to avoid a circular dependency.
 */
type UnauthorizedHandler = () => void
let unauthorizedHandler: UnauthorizedHandler | null = null

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler
}

/**
 * Perform a request against the GeneVerify API and return the raw response.
 *
 * Shared by the JSON helper and by binary endpoints (document downloads).
 * FormData bodies keep the browser-generated multipart boundary — no explicit
 * Content-Type header is set for them.
 */
async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = {}
  if (!(init.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }
  const token = getAccessToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: init.method ?? 'GET',
      headers,
      body: init.body,
    })
  } catch {
    throw new ApiError('Unable to reach the GeneVerify API. Is the backend running?')
  }

  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/login') {
      // Expired/revoked session: drop the stored token and notify the auth layer.
      clearAccessToken()
      unauthorizedHandler?.()
    }
    throw new ApiError(await extractErrorDetail(response), response.status)
  }
  return response
}

/**
 * Perform a typed request against the GeneVerify API.
 *
 * @param path API path relative to the versioned prefix, e.g. '/health'.
 */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await request(path, init)
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

/**
 * Perform a request and return the raw response (binary endpoints such as
 * document file downloads). Errors still surface as ApiError.
 */
export async function apiFetchRaw(path: string, init: RequestInit = {}): Promise<Response> {
  return request(path, init)
}
