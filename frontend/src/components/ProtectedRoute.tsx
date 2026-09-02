import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../context/AuthContext'

/**
 * Route guard: renders child routes only for authenticated users.
 * While the session is being restored a neutral splash is shown.
 */
export default function ProtectedRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="flex items-center gap-3 text-sm text-gray-500">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" aria-hidden="true" />
          Restoring session…
        </div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
