/**
 * Authentication service — the single entry point for auth API calls and
 * token lifecycle on the frontend.
 */

import { apiFetch } from './apiClient'
import { clearAccessToken, setAccessToken } from './tokenStorage'
import type { AuthUser, LoginResponse } from '../types/api'

/** Authenticate and persist the returned access token. */
export async function login(username: string, password: string): Promise<LoginResponse> {
  const response = await apiFetch<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  setAccessToken(response.access_token)
  return response
}

/** Re-validate the stored token against the backend. */
export async function fetchCurrentUser(): Promise<AuthUser> {
  return apiFetch<AuthUser>('/auth/me')
}

/**
 * Best-effort server logout, then always discard the token client-side.
 * (JWTs are stateless — the client dropping the token is what logs out.)
 */
export async function logout(): Promise<void> {
  try {
    await apiFetch<{ detail: string }>('/auth/logout', { method: 'POST' })
  } catch {
    // Network/401 failures must never block signing out.
  } finally {
    clearAccessToken()
  }
}
