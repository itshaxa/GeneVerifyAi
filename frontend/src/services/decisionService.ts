/**
 * Verification Decision Engine API service (Step 8).
 *
 * Calls the deterministic decision endpoints — NO AI/LLM involvement.
 */

import { apiFetch } from './apiClient'
import type { DecisionResponse } from '../types/api'

function decisionPath(verificationId: string): string {
  return `/verifications/${encodeURIComponent(verificationId)}/decision`
}

/** Trigger the evidence assessment for a case. */
export function runDecision(verificationId: string): Promise<DecisionResponse> {
  return apiFetch<DecisionResponse>(decisionPath(verificationId), { method: 'POST' })
}

/** Retrieve the current decision (if one exists). */
export function getDecision(verificationId: string): Promise<DecisionResponse> {
  return apiFetch<DecisionResponse>(decisionPath(verificationId))
}
