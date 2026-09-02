/**
 * DNA comparison service — submits structured STR evidence for one
 * verification case. The reference profile is always resolved server-side;
 * the client only ever sends the submitted profile.
 */

import { apiFetch } from './apiClient'
import type { DnaComparisonResponse } from '../types/api'

export function compareDna(
  verificationId: string,
  submittedProfile: unknown,
): Promise<DnaComparisonResponse> {
  return apiFetch<DnaComparisonResponse>(
    `/verifications/${encodeURIComponent(verificationId)}/dna/compare`,
    {
      method: 'POST',
      body: JSON.stringify({ submitted_profile: submittedProfile }),
    },
  )
}
