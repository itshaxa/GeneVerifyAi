/**
 * Health service — first concrete consumer of the API client.
 * Feature services (identity, verification, reports) follow this pattern.
 */

import { apiFetch } from './apiClient'
import type { HealthStatus } from '../types/api'

export function getHealthStatus(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>('/health')
}
