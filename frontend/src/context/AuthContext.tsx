/**
 * Frontend authentication state.
 *
 * Single source of truth for "who is logged in". On startup a stored token is
 * re-validated against GET /auth/me; any 401 from the API clears the session
 * and sends the user back to the login page.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

import { setUnauthorizedHandler } from '../services/apiClient'
import * as authService from '../services/authService'
import { getAccessToken } from '../services/tokenStorage'
import type { AuthUser } from '../types/api'

interface AuthContextValue {
  user: AuthUser | null
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()

  // React to any 401 from the API client: session is gone -> login page.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null)
      navigate('/login', { replace: true })
    })
    return () => setUnauthorizedHandler(null)
  }, [navigate])

  // Restore the session from a stored token, validating it server-side.
  useEffect(() => {
    if (!getAccessToken()) {
      setIsLoading(false)
      return
    }
    let cancelled = false
    authService
      .fetchCurrentUser()
      .then((currentUser) => {
        if (!cancelled) setUser(currentUser)
      })
      .catch(() => {
        if (!cancelled) setUser(null)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const response = await authService.login(username, password)
    setUser(response.user)
  }, [])

  const logout = useCallback(async () => {
    await authService.logout()
    setUser(null)
    navigate('/login', { replace: true })
  }, [navigate])

  const value = useMemo(
    () => ({ user, isLoading, login, logout }),
    [user, isLoading, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside <AuthProvider>')
  }
  return context
}
