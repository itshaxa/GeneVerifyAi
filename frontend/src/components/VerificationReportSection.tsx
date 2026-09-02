/**
 * Step 9: report summary card on the case detail page.
 * Step 10: presentational only. The page owns the one and only report request
 * through `useVerificationReport` and passes the payload down, so the pipeline,
 * the audit trail and this card read the same response instead of each issuing
 * their own `GET /verifications/{id}/report`.
 *
 * The PDF is still produced by the existing Step 9 endpoint - this card only
 * triggers it through `onDownload`. No second report implementation exists.
 */

import { Link } from 'react-router-dom'

import CaseStatusBadge from './CaseStatusBadge'
import { DecisionBadge } from './DecisionBadge'
import { DownloadIcon, FileTextIcon } from './Icons'
import { EmptyState, ErrorState, LoadingBlock } from './StateBlocks'
import type { VerificationReport } from '../types/api'
import {
  auditEventLabel,
  formatConsistency,
  formatPercent,
} from '../utils/reportFormat'

interface Props {
  report: VerificationReport | null
  isLoading: boolean
  isDownloading: boolean
  error: string | null
  /** Runs the existing PDF download endpoint. */
  onDownload: () => void
  /** Re-reads the report after a failure. */
  onRetry: () => void
}

export default function VerificationReportSection({
  report,
  isLoading,
  isDownloading,
  error,
  onDownload,
  onRetry,
}: Props) {
  const lastEvent = report?.audit_timeline[report.audit_timeline.length - 1]

  return (
    <section
      className="gv-card animate-gv-fade-up overflow-hidden"
      aria-labelledby="report-heading"
    >
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 bg-gray-50/60 px-5 py-4">
        <div className="flex items-start gap-3">
          <span
            className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700 ring-1 ring-brand-100"
            aria-hidden="true"
          >
            <FileTextIcon size={16} />
          </span>
          <div>
            <p className="gv-eyebrow">Stage 08 · Report</p>
            <h2 id="report-heading" className="gv-section-title mt-0.5">
              Verification Report
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Assembled by the server from the recorded evidence, decision and audit trail.
            </p>
          </div>
        </div>
        {report && <CaseStatusBadge status={report.status} />}
      </header>

      <div className="p-5 sm:p-6">
        {error && (
          <ErrorState message={error} onRetry={onRetry} retryLabel="Try again" className="mb-4" />
        )}

        {isLoading ? (
          <LoadingBlock label="Loading the verification report…" />
        ) : !report ? (
          !error && (
            <EmptyState
              icon={<FileTextIcon size={18} />}
              title="No report available yet"
              description="The report is generated on demand from the case data recorded so far."
            />
          )
        ) : (
          <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white">
            <dl className="grid grid-cols-1 gap-x-8 gap-y-4 px-5 py-4 sm:grid-cols-3">
              <Field label="Verification ID" value={report.verification_id} />
              <div>
                <dt className="gv-eyebrow">Decision</dt>
                <dd className="mt-1">
                  <DecisionBadge decision={report.decision.decision} />
                </dd>
              </div>
              <Field
                label="Evidence Score"
                value={
                  report.evidence.available
                    ? `${report.evidence.total_score} / ${report.evidence.max_score}`
                    : '— Not available'
                }
              />
              <Field
                label="DNA Match"
                value={
                  report.dna_analysis.available
                    ? formatPercent(report.dna_analysis.match_percentage)
                    : '— Not available'
                }
              />
              <Field label="Identity" value={formatConsistency(report.evidence.identity_consistency)} />
              <Field label="Document" value={formatConsistency(report.evidence.document_consistency)} />
            </dl>

            <div className="border-t border-gray-100 bg-gray-50/60 px-5 py-3 text-xs text-gray-500">
              Audit trail:{' '}
              <span className="font-medium text-gray-700">{report.audit_timeline.length}</span>{' '}
              recorded action{report.audit_timeline.length === 1 ? '' : 's'}
              {lastEvent ? ` — latest: ${auditEventLabel(lastEvent)}` : ''}
            </div>

            {/* Prominent primary action: the server-rendered PDF. */}
            <div className="flex flex-col gap-3 border-t border-gray-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs text-gray-500">
                Generating the PDF records a <span className="font-medium text-gray-700">Report generated</span>{' '}
                event in the audit trail.
              </p>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={onDownload}
                  disabled={isDownloading}
                  className="gv-btn gv-btn-primary gv-btn-lg w-full justify-center sm:w-auto"
                >
                  {isDownloading ? (
                    <span
                      className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
                      aria-hidden="true"
                    />
                  ) : (
                    <DownloadIcon size={16} />
                  )}
                  {isDownloading ? 'Generating PDF…' : 'Download PDF Report'}
                </button>
                <Link
                  to={`/verifications/${encodeURIComponent(report.verification_id)}/report`}
                  className="gv-btn gv-btn-secondary"
                >
                  View Full Report
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="gv-eyebrow">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold break-words text-gray-800">{value}</dd>
    </div>
  )
}
