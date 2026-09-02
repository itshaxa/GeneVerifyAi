/**
 * Step 9: full verification report page.
 *
 * Protected route (/verifications/:verificationId/report). Renders the nine
 * report sections defined by the report contract: header, identity, document,
 * AI extraction, DNA/STR analysis, evidence assessment, decision, audit
 * timeline and disclaimer.
 *
 * The page is a read-only view: loading it writes no audit event, and every
 * value shown comes from the API. Incomplete evidence is displayed as the
 * safe statement the backend produced - never as a fabricated result.
 *
 * Step 10: the report now arrives from the shared `useVerificationReport`
 * owner (no duplicate reads with the case page) and the PDF action is the
 * prominent primary button. No second report implementation was added.
 */

import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'

import AuditTimeline from '../components/AuditTimeline'
import CaseStatusBadge from '../components/CaseStatusBadge'
import { DownloadIcon, PrinterIcon } from '../components/Icons'
import { ErrorState, LoadingBlock } from '../components/StateBlocks'
import { useVerificationReport } from '../hooks/useVerificationReport'
import { formatTimestamp } from '../utils/format'
import {
  decisionBannerClasses,
  decisionIcon,
  formatClassification,
  formatConsistency,
  formatDecision,
  formatFileSize,
  formatPercent,
  humanizeCode,
} from '../utils/reportFormat'

export default function VerificationReportPage() {
  const { verificationId } = useParams<{ verificationId: string }>()
  // Same single report owner as the case page: this route only ever issues one
  // read, and the PDF still comes from the existing Step 9 endpoint.
  const { report, isLoading, isDownloading, error, refresh, downloadPdf } =
    useVerificationReport(verificationId)

  if (isLoading) {
    return (
      <div className="mx-auto w-full max-w-4xl">
        <LoadingBlock label="Building the report…" />
      </div>
    )
  }

  if (error && !report) {
    return (
      <div className="mx-auto w-full max-w-4xl">
        <ErrorState message={error} onRetry={refresh} retryLabel="Reload report" />
        <div className="mt-4">
          <Link to="/verifications" className="gv-btn gv-btn-secondary">
            ← Back to my cases
          </Link>
        </div>
      </div>
    )
  }

  if (!report) {
    return null
  }

  return (
    <div className="mx-auto w-full max-w-4xl">
      <nav className="mb-4 flex flex-wrap items-center justify-between gap-3 text-sm text-gray-500 print:hidden">
        <Link
          to={`/verifications/${encodeURIComponent(report.verification_id)}`}
          className="font-medium hover:text-brand-700"
        >
          ← Back to case {report.verification_id}
        </Link>
        <button
          type="button"
          onClick={() => window.print()}
          className="gv-btn gv-btn-sm gv-btn-secondary"
        >
          <PrinterIcon size={14} />
          Print
        </button>
      </nav>

      {error && (
        <div className="mb-4">
          <ErrorState message={error} onRetry={refresh} retryLabel="Reload report" />
        </div>
      )}

      <article className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
        {/* 1. Report header */}
        <header className="border-b border-gray-200 bg-gray-50 px-6 py-6 sm:px-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-brand-700">
                GeneVerify AI
              </p>
              <h1 className="mt-1 text-2xl font-semibold tracking-tight text-gray-900">
                Verification Report
              </h1>
              <p className="mt-2 text-sm text-gray-500">
                DNA identity verification — prototype evidence assessment
              </p>
            </div>
            <CaseStatusBadge status={report.status} />
          </div>
          <dl className="mt-5 grid grid-cols-1 gap-4 text-sm sm:grid-cols-3">
            <HeaderField label="Verification ID" value={report.verification_id} />
            <HeaderField label="Decision" value={formatDecision(report.decision.decision)} />
            <HeaderField label="Generated" value={formatTimestamp(report.generated_at)} />
          </dl>

          {/* Prominent report action (hidden when printing the page itself). */}
          <div className="mt-6 flex flex-col gap-3 rounded-xl border border-brand-100 bg-white px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs leading-relaxed text-gray-500">
              The PDF is rendered by the server from the data above and records a{' '}
              <span className="font-medium text-gray-700">Report generated</span> audit event.
            </p>
            <button
              type="button"
              onClick={() => void downloadPdf()}
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
          </div>
        </header>

        {/* 2. Identity summary */}
        <Section index={1} title="Identity Information">
          <div className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
            <Row label="Name" value={report.identity.name} />
            <Row label="Father's name" value={report.identity.father_name} />
            <Row label="Date of birth" value={report.identity.date_of_birth} />
            <Row label="Gender" value={humanizeCode(report.identity.gender)} />
            <Row label="CNIC" value={report.identity.cnic} />
            <Row label="Record status" value={humanizeCode(report.identity.identity_status)} />
          </div>
        </Section>

        {/* 3. Document analysis */}
        <Section index={2} title="Document Information" tone>
          {report.document.available ? (
            <div className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
              <Row label="Document ID" value={report.document.document_id} />
              <Row label="Original filename" value={report.document.original_filename} />
              <Row label="Document type" value={humanizeCode(report.document.document_type)} />
              <Row label="File format" value={report.document.content_type} />
              <Row label="File size" value={formatFileSize(report.document.file_size)} />
              <Row label="Processing status" value={humanizeCode(report.document.processing_status)} />
              <Row label="Uploaded by" value={report.document.uploaded_by} />
              <Row label="Upload timestamp" value={formatTimestampOrNull(report.document.uploaded_at)} />
            </div>
          ) : (
            <Unavailable message={report.document.message} />
          )}
        </Section>

        {/* 4. AI extraction summary */}
        <Section index={3} title="AI Extraction">
          {report.ai_extraction.available ? (
            <>
              <AiLabel text={report.ai_extraction.label} />
              <div className="mt-4 grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
                <Row label="Extraction status" value={humanizeCode(report.ai_extraction.extraction_status)} />
                <Row label="AI model used" value={report.ai_extraction.model_name} />
                <Row label="Extracted name" value={report.ai_extraction.extracted_name} />
                <Row label="Extracted CNIC" value={report.ai_extraction.extracted_cnic} />
                <Row label="CNIC consistency" value={formatConsistency(report.ai_extraction.cnic_consistency)} />
                <Row label="Name consistency" value={formatConsistency(report.ai_extraction.name_consistency)} />
                <Row label="Identity consistency" value={formatConsistency(report.ai_extraction.identity_consistency)} />
                <Row label="STR markers extracted" value={String(report.ai_extraction.extracted_marker_count)} />
              </div>
              {report.ai_extraction.validation_note && (
                <p className="mt-3 text-xs text-gray-500">{report.ai_extraction.validation_note}</p>
              )}
            </>
          ) : (
            <Unavailable message={report.ai_extraction.message} />
          )}
        </Section>

        {/* 5. DNA analysis */}
        <Section index={4} title="DNA / STR Analysis" tone>
          {report.dna_analysis.available ? (
            <>
              <div className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs text-brand-800">
                {report.dna_analysis.engine_note}
              </div>
              <div className="mt-4 grid grid-cols-2 gap-x-8 gap-y-3 sm:grid-cols-3">
                <Row label="Classification" value={formatClassification(report.dna_analysis.classification)} />
                <Row label="Match percentage" value={formatPercent(report.dna_analysis.match_percentage)} />
                <Row label="Total markers" value={String(report.dna_analysis.total_markers ?? '—')} />
                <Row label="Matched markers" value={String(report.dna_analysis.matched_markers ?? '—')} />
                <Row label="Mismatched markers" value={String(report.dna_analysis.mismatched_markers ?? '—')} />
                <Row label="Missing markers" value={String(report.dna_analysis.missing_markers ?? '—')} />
                {report.dna_analysis.invalid_markers ? (
                  <Row label="Invalid markers" value={String(report.dna_analysis.invalid_markers)} />
                ) : null}
                <Row label="Compared at" value={formatTimestampOrNull(report.dna_analysis.compared_at)} />
              </div>
              <p className="mt-3 text-xs text-gray-500">
                Aggregate results only — raw allele values are not reproduced in reports.
              </p>
            </>
          ) : (
            <Unavailable message={report.dna_analysis.message} />
          )}
        </Section>

        {/* 6. Evidence assessment */}
        <Section index={5} title="Evidence Assessment">
          {report.evidence.available ? (
            <>
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
                    {report.evidence.score_label}
                  </p>
                  <p className="mt-1 text-3xl font-bold text-gray-900">
                    {report.evidence.total_score}{' '}
                    <span className="text-base font-normal text-gray-500">
                      / {report.evidence.max_score}
                    </span>
                  </p>
                </div>
                <p className="max-w-xs text-xs text-gray-500">{report.evidence.score_note}</p>
              </div>
              <div className="mt-5 space-y-4">
                <ScoreBar
                  label="DNA STR comparison"
                  points={report.evidence.dna_score}
                  maximum={70}
                  detail={`${formatClassification(report.evidence.dna_classification)} · ${formatPercent(report.evidence.dna_match_percentage)}`}
                />
                <ScoreBar
                  label="Identity information consistency"
                  points={report.evidence.identity_score}
                  maximum={20}
                  detail={formatConsistency(report.evidence.identity_consistency)}
                />
                <ScoreBar
                  label="Document consistency"
                  points={report.evidence.document_score}
                  maximum={10}
                  detail={formatConsistency(report.evidence.document_consistency)}
                />
              </div>
            </>
          ) : (
            <Unavailable message={report.evidence.message} />
          )}
        </Section>

        {/* 7. Final decision */}
        <Section index={6} title="Final Decision" tone>
          {report.decision.available ? (
            <>
              <div
                className={`flex items-center gap-3 rounded-xl px-4 py-3 ${decisionBannerClasses(report.decision.decision)}`}
              >
                <span className="text-lg" aria-hidden="true">
                  {decisionIcon(report.decision.decision)}
                </span>
                <span className="text-base font-semibold">
                  {formatDecision(report.decision.decision)}
                </span>
                {report.decision.decided_at && (
                  <span className="ml-auto text-xs opacity-75">
                    {formatTimestamp(report.decision.decided_at)}
                  </span>
                )}
              </div>
              <p className="mt-4 text-sm leading-relaxed text-gray-700">
                {report.decision.explanation}
              </p>
            </>
          ) : (
            <Unavailable message={report.decision.message} />
          )}
        </Section>

        {/* 8. Audit timeline */}
        <Section index={7} title="Audit Timeline">
          <AuditTimeline events={report.audit_timeline} />
        </Section>

        {/* 9. Disclaimer */}
        <footer className="border-t border-gray-200 bg-gray-50 px-6 py-5 sm:px-8">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">Disclaimer</h2>
          <p className="mt-2 text-xs leading-relaxed text-gray-600">{report.disclaimer}</p>
          <p className="mt-3 text-[11px] text-gray-400">
            Report generated {formatTimestamp(report.generated_at)} from evidence stored in the
            GeneVerify AI case record.
          </p>
        </footer>
      </article>
    </div>
  )
}

// --- Building blocks ------------------------------------------------------------

function Section({
  index,
  title,
  tone = false,
  children,
}: {
  index: number
  title: string
  tone?: boolean
  children: ReactNode
}) {
  return (
    <section
      className={`border-b border-gray-100 px-6 py-6 sm:px-8 ${tone ? 'bg-gray-50/60' : 'bg-white'}`}
    >
      <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-brand-600 text-[11px] font-semibold text-white">
          {index}
        </span>
        {title}
      </h2>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function HeaderField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className="mt-0.5 font-mono text-sm font-semibold text-gray-900">{value}</dd>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className="mt-0.5 text-sm break-words text-gray-800">{value || '—'}</dd>
    </div>
  )
}

function Unavailable({ message }: { message: string | null | undefined }) {
  return (
    <p className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 text-sm text-gray-500">
      {message ?? 'Not available.'}
    </p>
  )
}

function AiLabel({ text }: { text: string }) {
  return (
    <p className="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-800">
      <span aria-hidden="true">AI</span>
      {text}
    </p>
  )
}

function ScoreBar({
  label,
  points,
  maximum,
  detail,
}: {
  label: string
  points: number
  maximum: number
  detail: string
}) {
  const ratio = maximum > 0 ? Math.min(Math.max(points / maximum, 0), 1) : 0
  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
        <span className="font-medium text-gray-800">{label}</span>
        <span className="text-xs text-gray-500">
          {detail} · <span className="font-semibold text-gray-800">{points}</span> / {maximum}
        </span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-gray-100">
        <div
          className="h-full rounded-full bg-brand-500"
          style={{ width: `${ratio * 100}%` }}
          aria-hidden="true"
        />
      </div>
    </div>
  )
}

function formatTimestampOrNull(value: string | null): string {
  return value ? formatTimestamp(value) : '—'
}
