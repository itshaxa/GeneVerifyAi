/**
 * Step 8: Verification Assessment section — deterministic evidence scoring.
 * Step 10: same data, presented as the pipeline's Evidence + Decision stages
 * with a single prominent result card.
 *
 * Combines Step 5 (DNA STR comparison) and Step 7 (document extraction
 * consistency) into the transparent Prototype Evidence Score and the final
 * VERIFIED / REVIEW_REQUIRED / MISMATCH decision.
 *
 * The score, the classification and the explanation are read straight from
 * `POST/GET /verifications/{id}/decision`. Nothing is recomputed here - the
 * backend is the only authority for the outcome. NO AI/LLM produces it.
 */

import { useCallback, useEffect, useState } from 'react'

import DNAHelixAnimation from './DNAHelixAnimation'
import { ApiError } from '../services/apiClient'
import { getDecision, runDecision } from '../services/decisionService'
import type { DecisionResponse } from '../types/api'
import {
  decisionBannerClasses,
  formatClassification,
  formatConsistency,
  formatDecision,
  formatPercent,
} from '../utils/reportFormat'
import { describeError, isNotFound } from '../utils/errorMessage'
import { AlertIcon, CheckCircleIcon, ClockIcon, ScaleIcon, XIcon } from './Icons'
import { EmptyState, ErrorState, LoadingBlock } from './StateBlocks'

interface Props {
  verificationId: string
  /** Called after a successful decision to let the parent refresh case status. */
  onDecided?: () => void
}

export default function VerificationAssessmentSection({ verificationId, onDecided }: Props) {
  const [decision, setDecision] = useState<DecisionResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // A failed *read* is kept apart from "nothing recorded yet" so a transient
  // outage is never presented as an empty assessment.
  const [loadError, setLoadError] = useState<string | null>(null)

  // Load existing decision on mount (no AI cost — just DB read)
  const loadExisting = useCallback(async () => {
    setIsLoading(true)
    setLoadError(null)
    try {
      const result = await getDecision(verificationId)
      setDecision(result)
    } catch (err) {
      setDecision(null)
      if (!isNotFound(err)) {
        // 404 means "no decision yet", which is an ordinary state; anything
        // else is a real failure and has to be shown with a retry.
        setLoadError(describeError(err, 'The recorded assessment could not be loaded.'))
      }
    } finally {
      setIsLoading(false)
    }
  }, [verificationId])

  useEffect(() => {
    void loadExisting()
  }, [loadExisting])

  async function handleRun() {
    setIsRunning(true)
    setError(null)
    try {
      const result = await runDecision(verificationId)
      setDecision(result)
      onDecided?.()
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Failed to run the verification assessment.',
      )
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <section className="gv-card animate-gv-fade-up overflow-hidden" aria-labelledby="assessment-heading">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 bg-gray-50/60 px-5 py-4">
        <div className="flex items-start gap-3">
          <span
            className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700 ring-1 ring-brand-100"
            aria-hidden="true"
          >
            <ScaleIcon size={16} />
          </span>
          <div>
            <p className="gv-eyebrow">Stage 06 · Evidence — Stage 07 · Decision</p>
            <h2 id="assessment-heading" className="gv-section-title mt-0.5">
              Evidence assessment &amp; verification decision
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Deterministic scoring of DNA, identity and document evidence. No AI decides the outcome.
            </p>
          </div>
        </div>
      </header>

      <div className="p-5 sm:p-6">
        {/* Decorative helix bound to the existing decision run; the outcome below is the backend's. */}
        <DNAHelixAnimation active={isRunning} className="mb-3 h-36 w-full sm:h-44" />

        {error && <ErrorState message={error} className="mb-4" />}

        {isLoading ? (
          <LoadingBlock label="Loading the recorded assessment…" />
        ) : loadError ? (
          <ErrorState
            message={loadError}
            onRetry={() => void loadExisting()}
            retryLabel="Reload assessment"
          />
        ) : !decision ? (
          <EmptyState
            icon={<ScaleIcon size={18} />}
            title="No evidence assessment recorded yet"
            description="Assessment becomes available once a document has been analysed and the STR comparison has run."
            actionLabel={isRunning ? 'Assessing…' : 'Run Verification Assessment'}
            onAction={() => void handleRun()}
          />
        ) : (
          <DecisionCard decision={decision} onRerun={() => void handleRun()} isRunning={isRunning} />
        )}
      </div>
    </section>
  )
}

// --- Final result card (Step 10 requirement 7) -------------------------------------

const RESULT_ACCENTS: Record<string, string> = {
  VERIFIED: 'bg-brand-600',
  REVIEW_REQUIRED: 'bg-amber-500',
  MISMATCH: 'bg-red-600',
}

function ResultGlyph({ outcome }: { outcome: string }) {
  const className = 'h-6 w-6'
  if (outcome === 'VERIFIED') return <CheckCircleIcon className={className} size={24} />
  if (outcome === 'MISMATCH') return <XIcon className={className} size={24} />
  if (outcome === 'REVIEW_REQUIRED') return <ClockIcon className={className} size={24} />
  return <AlertIcon size={24} />
}

function DecisionCard({
  decision,
  onRerun,
  isRunning,
}: {
  decision: DecisionResponse
  onRerun: () => void
  isRunning: boolean
}) {
  const {
    decision: outcome,
    evidence_score,
    dna_classification,
    dna_match_percentage,
    identity_consistency,
    document_consistency,
    explanation,
  } = decision

  // Visual clamp only - the value itself is the backend's.
  const scoreWidth = Math.max(0, Math.min(100, evidence_score))

  return (
    <div className="animate-gv-pop overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
      {/* Headline: outcome + evidence score */}
      <div className={`px-5 py-5 sm:px-6 ${decisionBannerClasses(outcome)}`}>
        <div className="flex flex-wrap items-center gap-4">
          <span
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/75 shadow-sm"
            aria-hidden="true"
          >
            <ResultGlyph outcome={outcome} />
          </span>
          <div className="min-w-0">
            <p className="gv-eyebrow opacity-70">Final verification result</p>
            <p className="text-2xl font-bold tracking-tight sm:text-3xl">
              {formatDecision(outcome)}
            </p>
          </div>
          <div className="ml-auto text-right">
            <p className="gv-eyebrow opacity-70">Evidence Score</p>
            <p className="text-3xl font-bold tabular-nums sm:text-4xl">
              {evidence_score}
              <span className="text-base font-medium opacity-70"> / 100</span>
            </p>
          </div>
        </div>
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/60">
          <div
            className={`h-full rounded-full transition-[width] duration-700 ease-out ${RESULT_ACCENTS[outcome] ?? 'bg-gray-500'}`}
            style={{ width: `${scoreWidth}%` }}
          />
        </div>
      </div>

      {/* Evidence breakdown */}
      <div className="grid grid-cols-1 gap-px bg-gray-100 sm:grid-cols-3">
        <EvidenceItem
          label="DNA"
          value={formatClassification(dna_classification)}
          sub={dna_match_percentage != null ? formatPercent(dna_match_percentage) : undefined}
        />
        <EvidenceItem label="Identity" value={formatConsistency(identity_consistency)} />
        <EvidenceItem label="Document" value={formatConsistency(document_consistency)} />
      </div>

      {/* Backend explanation - never rewritten or replaced by a client-side one */}
      <div className="border-t border-gray-100 px-5 py-4 sm:px-6">
        <p className="gv-eyebrow">Why this result</p>
        <p className="mt-1 text-sm leading-relaxed text-gray-700">{explanation}</p>
      </div>

      {/* Disclaimer */}
      <div className="border-t border-gray-100 bg-gray-50 px-5 py-3 sm:px-6">
        <p className="text-xs leading-relaxed text-gray-500">
          Important: Prototype evidence score — not a forensic probability. This is a hackathon
          prototype using synthetic demonstration data and is not a legally valid forensic identity
          system.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 px-5 py-3 sm:px-6">
        <p className="text-xs text-gray-400">
          Deterministic Decision Engine · outcome stored with the case
        </p>
        <button type="button" onClick={onRerun} disabled={isRunning} className="gv-btn gv-btn-sm gv-btn-secondary">
          {isRunning ? 'Re-assessing…' : 'Re-run Assessment'}
        </button>
      </div>
    </div>
  )
}

function EvidenceItem({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="min-w-0 bg-white px-5 py-4">
      <p className="gv-eyebrow">{label}</p>
      <p className="mt-1 text-sm font-semibold break-words text-gray-900">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-500">{sub}</p>}
    </div>
  )
}
