/**
 * Identity lookup service — CNIC-only retrieval of a single synthetic record.
 * The backend never exposes a list/export of the identity database.
 */

import { apiFetch } from './apiClient'
import type { IdentityLookupResponse } from '../types/api'

export function lookupIdentityByCnic(cnic: string): Promise<IdentityLookupResponse> {
  return apiFetch<IdentityLookupResponse>(`/identity/${encodeURIComponent(cnic.trim())}`)
}
