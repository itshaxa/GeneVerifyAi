/**
 * Verification report API service (Step 9).
 *
 * Two distinct operations, deliberately separated:
 *
 *  * `getReport`      - a pure read. The backend writes no audit event here,
 *                       so refreshing the report page cannot inflate the
 *                       case timeline.
 *  * `downloadReport` - an explicit generation. The backend renders the PDF
 *                       server-side and records one REPORT_GENERATED event.
 *
 * The frontend never assembles report content and never sees DNA allele
 * values, storage paths or credentials - the API contract has no such fields.
 */

import { apiFetch, apiFetchRaw } from './apiClient'
import type { VerificationReport } from '../types/api'

function reportPath(verificationId: string): string {
  return `/verifications/${encodeURIComponent(verificationId)}/report`
}

/** Structured JSON report of an accessible case (read-only). */
export function getReport(verificationId: string): Promise<VerificationReport> {
  return apiFetch<VerificationReport>(reportPath(verificationId))
}

/** Fetch the generated PDF bytes; the browser never sees a server path. */
export async function downloadReport(verificationId: string): Promise<Blob> {
  const response = await apiFetchRaw(`${reportPath(verificationId)}/download`)
  return response.blob()
}

/** Generate the PDF and hand it to the browser as a file download. */
export async function saveReportPdf(verificationId: string): Promise<void> {
  const blob = await downloadReport(verificationId)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `GeneVerify-Report-${verificationId}.pdf`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  // Give the browser time to start the download before releasing the blob.
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
