/**
 * Access-token storage — the ONLY module that knows where tokens live.
 *
 * Prototype tradeoff: tokens are kept in localStorage for simplicity. This is
 * vulnerable to XSS and is NOT acceptable for a production system; the plan
 * is to upgrade to HttpOnly cookie sessions before deployment. Because every
 * read/write/clear goes through this module, that upgrade only touches this
 * file plus the API client — not the rest of the application.
 */

const TOKEN_STORAGE_KEY = 'geneverify.accessToken'

export function getAccessToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    // Storage unavailable (e.g. privacy mode) — treat as signed out.
    return null
  }
}

export function setAccessToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token)
  } catch {
    // Ignore write failures; the in-memory auth state still works per-tab.
  }
}

export function clearAccessToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY)
  } catch {
    // Nothing to clean up.
  }
}
