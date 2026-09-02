/**
 * Verification case detail — the operational heart of Step 10.
 *
 * The page is a layout: case header, pipeline, then the seven workflow stages
 * in order. Every section talks to its own existing endpoint and this page
 * holds no business logic — no scoring, no classification, no derived status.
 *
 * It owns exactly one report request (`useVerificationReport`) and hands the
 * payload to the pipeline, the audit trail and the report card, which earlier
 * each fetched the same endpoint independently.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import AuditTimeline from '../components/AuditTimeline'
import CaseStatusBadge from '../components/CaseStatusBadge'
import { DecisionBadge } from '../components/DecisionBadge'
import DnaAnalysisSection from '../components/DnaAnalysisSection'
import DocumentsSection from '../components/DocumentsSection'
import { ClockIcon, RefreshIcon, ShieldIcon, UserIcon } from '../components/Icons'
import { ErrorState, LoadingBlock, SectionCard } from '../components/StateBlocks'
import VerificationAssessmentSection from '../components/VerificationAssessmentSection'
import VerificationPipeline from '../components/VerificationPipeline'
import VerificationReportSection from '../components/VerificationReportSection'
import { useVerificationReport } from '../hooks/useVerificationReport'
import { ApiError } from '../services/apiClient'
import { getVerification } from '../services/verificationService'
import { formatRelative, formatTimestamp } from '../utils/format'
import type { VerificationCase } from '../types/api'

/** Read-only detail view of one accessible verification case. */
export default function VerificationCaseDetailPage() {
  const { verificationId } = useParams<{ verificationId: string }>()
  const [verificationCase, setVerificationCase] = useState<VerificationCase | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Single owner of GET /verifications/{id}/report for this screen.
  const { report, isLoading: isReportLoading, isDownloading, error: reportError, refresh: refreshReport, downloadPdf } =
    useVerificationReport(verificationId)

  const load = useCallback(
    async (silent = false) => {
      if (!verificationId) return
      // Silent refreshes (e.g. after a DNA comparison) must not remount the
      // page, otherwise freshly rendered section results disappear.
      if (!silent) {
        setIsLoading(true)
        setError(null)
      }
      try {
        setVerificationCase(await getVerification(verificationId))
      } catch (err) {
        if (!silent) {
          setError(err instanceof ApiError ? err.message : 'Failed to load the verification case.')
        }
      } finally {
        if (!silent) setIsLoading(false)
      }
    },
    [verificationId],
  )

  useEffect(() => {
    void load()
  }, [load])

  /** Silent case refresh plus a refresh of the shared report payload. */
  const refresh = useCallback(() => {
    void load(true)
    refreshReport()
  }, [load, refreshReport])

  if (isLoading) {
    return (
      <div className="mx-auto w-full max-w-5xl">
        <LoadingBlock label="Loading case…" />
      </div>
    )
  }

  if (error || !verificationCase) {
    return (
      <div className="mx-auto w-full max-w-5xl">
        <ErrorState
          message={error ?? 'Case not found.'}
          onRetry={() => void load()}
          retryLabel="Retry"
          className="py-10"
        />
        <div className="mt-4">
          <Link to="/verifications" className="gv-btn gv-btn-secondary">
            ← Back to my cases
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <nav className="text-sm text-gray-500" aria-label="Breadcrumb">
        <Link to="/verifications" className="font-medium hover:text-brand-700">
          ← My verification cases
        </Link>
      </nav>

      {/* --- CASE HEADER ----------------------------------------------------- */}
      <header className="gv-card animate-gv-fade-up overflow-hidden">
        <div className="bg-gradient-to-br from-white via-white to-brand-50/60 px-5 py-5 sm:px-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="gv-eyebrow">Verification case</p>
              <h1 className="mt-1 truncate font-mono text-xl font-semibold tracking-tight text-gray-900 sm:text-2xl">
                {verificationCase.verification_id}
              </h1>
              <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-gray-500">
                <span className="inline-flex items-center gap-1">
                  <UserIcon size={13} />
                  {verificationCase.created_by_username}
                </span>
                <span aria-hidden="true">·</span>
                <span className="inline-flex items-center gap-1">
                  <ClockIcon size={13} />
                  Updated {formatRelative(verificationCase.updated_at)}
                </span>
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <CaseStatusBadge status={verificationCase.status} size="lg" />
              {/* Read from the report payload — never derived on the client. */}
              <DecisionBadge decision={report?.decision.decision} size="lg" />
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={refresh}
              className="gv-btn gv-btn-sm gv-btn-secondary"
            >
              <RefreshIcon size={14} />
              Refresh
            </button>
            <Link to="/verify" className="gv-btn gv-btn-sm gv-btn-ghost">
              Start another verification
            </Link>
            <span className="gv-badge bg-gray-100 text-gray-600 ring-gray-300 sm:ml-auto">
              <ShieldIcon size={13} />
              Prototype · synthetic data
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-px border-t border-gray-100 bg-gray-100 sm:grid-cols-2 lg:grid-cols-3">
          <div className="bg-white px-5 py-4">
            <p className="gv-eyebrow">Identity on record</p>
            <p className="mt-1 text-sm font-semibold text-gray-900">{verificationCase.identity.name}</p>
            <p className="text-sm text-gray-500">Father: {verificationCase.identity.father_name}</p>
          </div>
          <div className="bg-white px-5 py-4">
            <p className="gv-eyebrow">CNIC</p>
            <p className="mt-1 font-mono text-sm font-semibold text-gray-900">
              {verificationCase.identity.cnic}
            </p>
            <p className="text-xs text-gray-500">
              Identity status: {verificationCase.identity.status}
            </p>
          </div>
          <div className="bg-white px-5 py-4">
            <p className="gv-eyebrow">Registered</p>
            <p className="mt-1 text-sm font-semibold text-gray-900">
              {formatTimestamp(verificationCase.created_at)}
            </p>
            <p className="text-xs text-gray-500">
              {verificationCase.identity.date_of_birth} · {verificationCase.identity.gender}
            </p>
          </div>
        </div>
      </header>

      {/* --- PIPELINE -------------------------------------------------------- */}
      <VerificationPipeline
        variant="case"
        report={report}
        loading={isReportLoading}
        unavailable={!isReportLoading && !report && Boolean(reportError)}
      />

      {/* --- STAGES 03 / 04: DOCUMENT + AI EXTRACTION ------------------------ */}
      <DocumentsSection verificationId={verificationCase.verification_id} onCompared={refresh} />

      {/* --- STAGE 05: DNA ANALYSIS ----------------------------------------- */}
      <DnaAnalysisSection verificationId={verificationCase.verification_id} onCompared={refresh} />

      {/* --- STAGES 06 / 07: EVIDENCE ASSESSMENT + DECISION ----------------- */}
      <VerificationAssessmentSection
        verificationId={verificationCase.verification_id}
        onDecided={refresh}
      />

      {/* --- AUDIT TRAIL ----------------------------------------------------- */}
      <SectionCard
        eyebrow="Append-only history"
        title="Audit trail"
        description="Every recorded action on this case, exactly as stored by the server."
        headingLevel="h2"
      >
        {isReportLoading ? (
          <LoadingBlock label="Loading the audit trail…" variant="row" />
        ) : reportError && !report ? (
          <ErrorState message={reportError} onRetry={refreshReport} retryLabel="Reload trail" />
        ) : (
          <AuditTimeline events={report?.audit_timeline ?? []} />
        )}
      </SectionCard>

      {/* --- STAGE 08: REPORT ------------------------------------------------ */}
      <VerificationReportSection
        report={report}
        isLoading={isReportLoading}
        isDownloading={isDownloading}
        error={reportError}
        onDownload={() => void downloadPdf()}
        onRetry={refreshReport}
      />
    </div>
  )
}
