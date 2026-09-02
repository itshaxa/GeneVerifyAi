import { useEffect, useState } from 'react'

import { ApiError } from '../services/apiClient'
import { getHealthStatus } from '../services/healthService'
import type { HealthStatus } from '../types/api'

export interface HealthCheckState {
  health: HealthStatus | null
  isLoading: boolean
  error: string | null
}

/** Fetch backend health once on mount; used by the shell status indicator. */
export function useHealthCheck(): HealthCheckState {
  const [state, setState] = useState<HealthCheckState>({
    health: null,
    isLoading: true,
    error: null,
  })

  useEffect(() => {
    let cancelled = false

    getHealthStatus()
      .then((health) => {
        if (!cancelled) {
          setState({ health, isLoading: false, error: null })
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          const message =
            error instanceof ApiError
              ? error.message
              : 'Unexpected error while contacting the GeneVerify API.'
          setState({ health: null, isLoading: false, error: message })
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  return state
}
