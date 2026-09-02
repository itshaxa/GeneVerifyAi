/**
 * Verification case service — create, list and inspect the current user's
 * verification cases. The backend enforces ownership; the frontend never
 * sends or trusts user identifiers.
 */

import { apiFetch } from './apiClient'
import type { VerificationCase, VerificationCaseListResponse } from '../types/api'

export function createVerification(cnic: string): Promise<VerificationCase> {
  return apiFetch<VerificationCase>('/verifications', {
    method: 'POST',
    body: JSON.stringify({ cnic: cnic.trim() }),
  })
}

export function listVerifications(): Promise<VerificationCaseListResponse> {
  return apiFetch<VerificationCaseListResponse>('/verifications')
}

export function getVerification(verificationId: string): Promise<VerificationCase> {
  return apiFetch<VerificationCase>(`/verifications/${encodeURIComponent(verificationId)}`)
}
