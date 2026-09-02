/**
 * Step 10: one owner for the verification report of a case.
 *
 * Before this hook, the report was fetched independently by the report card
 * and by the report page, so a single screen issued the same read several
 * times over. A page now loads it once and passes the result to the pipeline,
 * the audit timeline and the report preview, which all read the same payload.
 *
 * `downloadPdf` still calls the existing Step 9 download endpoint only - the
 * PDF keeps being generated server-side, and the silent reload afterwards is
 * what makes the freshly recorded REPORT_GENERATED event appear in the
 * timeline.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { getReport, saveReportPdf } from '../services/reportService'
import type { VerificationReport } from '../types/api'
import { describeError } from '../utils/errorMessage'

export interface VerificationReportState {
  report: VerificationReport | null
  isLoading: boolean
  isDownloading: boolean
  error: string | null
  /** Re-read the report without showing a loading state. */
  refresh: () => void
  /** Generate the PDF through the existing API, then refresh the timeline. */
  downloadPdf: () => Promise<void>
}

export function useVerificationReport(
  verificationId: string | null | undefined,
): VerificationReportState {
  const [report, setReport] = useState<VerificationReport | null>(null)
  const [isLoading, setIsLoading] = useState(Boolean(verificationId))
  const [isDownloading, setIsDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const requestId = useRef(0)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const load = useCallback(
    async (silent: boolean) => {
      if (!verificationId) {
        setReport(null)
        setIsLoading(false)
        return
      }
      const currentRequest = ++requestId.current
      if (!silent) setIsLoading(true)
      setError(null)
      try {
        const result = await getReport(verificationId)
        if (mounted.current && currentRequest === requestId.current) setReport(result)
      } catch (err: unknown) {
        if (mounted.current && currentRequest === requestId.current) {
          setError(describeError(err, 'Unable to load the verification report.'))
        }
      } finally {
        if (mounted.current && currentRequest === requestId.current && !silent) setIsLoading(false)
      }
    },
    [verificationId],
  )

  useEffect(() => {
    void load(false)
  }, [load])

  const downloadPdf = useCallback(async () => {
    if (!verificationId || isDownloading) return
    setIsDownloading(true)
    setError(null)
    try {
      await saveReportPdf(verificationId)
      // The download appended a REPORT_GENERATED event server-side.
      await load(true)
    } catch (err: unknown) {
      if (mounted.current) {
        setError(describeError(err, 'Unable to generate the PDF report.'))
      }
    } finally {
      if (mounted.current) setIsDownloading(false)
    }
  }, [verificationId, isDownloading, load])

  return {
    report,
    isLoading,
    isDownloading,
    error,
    refresh: () => void load(true),
    downloadPdf,
  }
}
