/**
 * Step 10: the Command Center overview data.
 *
 * The backend exposes no aggregate statistics endpoint, and a case's own
 * `status` cannot separate a VERIFIED outcome from a MISMATCH (the Step 8
 * engine maps both to COMPLETED). So the honest source of truth is:
 *
 *   1. `GET /verifications`        - every case this user may see (admins see
 *                                    all), newest first. Status counts come
 *                                    straight from this response.
 *   2. `GET /verifications/{id}/decision` - read once per case that can
 *                                    already hold a decision, so Verified and
 *                                    Mismatch are counted from stored
 *                                    outcomes, never guessed.
 *
 * Nothing here invents a number: step (2) is bounded, and whenever it could
 * not cover every eligible case the hook reports `decisionCoverage.skipped`
 * so the UI can state its own basis.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { getDecision } from '../services/decisionService'
import { listVerifications } from '../services/verificationService'
import type { DecisionOutcome, VerificationCase } from '../types/api'
import { describeError, isNotFound } from '../utils/errorMessage'

/** Maximum per-case decision reads for a single overview calculation. */
const DECISION_LOOKUP_LIMIT = 40

/**
 * Only a completed or review-required case can hold a decision: recording a
 * decision always moves the case to one of those two statuses (the backend's
 * `_update_case_status`), and a comparison only ever advances a draft to
 * `in_progress`. Reading the others would ask for something that cannot exist.
 */
function couldHaveDecision(item: VerificationCase): boolean {
  return item.status === 'completed' || item.status === 'review_required'
}

export interface CaseOverviewCounts {
  total: number
  draft: number
  inProgress: number
  reviewRequired: number
  completed: number
  cancelled: number
  verified: number
  mismatch: number
  decisionReviewRequired: number
  decided: number
  awaitingDecision: number
}

export interface DecisionCoverage {
  /** Eligible cases actually read from the decision endpoint. */
  checked: number
  /** Ids of those cases, so a view can tell "no decision" from "not read". */
  checkedIds: string[]
  /** Eligible cases in total. */
  eligible: number
  /** Eligible cases left unread because of the lookup bound. */
  skipped: number
  /** Reads that failed for a reason other than "no decision yet". */
  failed: number
}

export interface CaseOverviewState {
  cases: VerificationCase[]
  counts: CaseOverviewCounts
  /** verification_id -> decision outcome, for the cases that have one. */
  decisions: Record<string, DecisionOutcome>
  isLoadingCases: boolean
  isCalculatingOutcomes: boolean
  error: string | null
  decisionCoverage: DecisionCoverage
  refresh: () => void
}

export function useCaseOverview(): CaseOverviewState {
  const [cases, setCases] = useState<VerificationCase[]>([])
  const [decisions, setDecisions] = useState<Record<string, DecisionOutcome>>({})
  const [isLoadingCases, setIsLoadingCases] = useState(true)
  const [isCalculatingOutcomes, setIsCalculatingOutcomes] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [decisionCoverage, setDecisionCoverage] = useState<DecisionCoverage>({
    checked: 0,
    checkedIds: [],
    eligible: 0,
    skipped: 0,
    failed: 0,
  })

  // Guards against a slow earlier response overwriting a newer one.
  const requestId = useRef(0)

  const load = useCallback(async () => {
    const currentRequest = ++requestId.current
    setIsLoadingCases(true)
    setError(null)

    let items: VerificationCase[] = []
    try {
      const response = await listVerifications()
      items = response.items
      setCases(items)
    } catch (err: unknown) {
      if (currentRequest === requestId.current) {
        setError(describeError(err, 'Unable to load your verification cases.'))
        setCases([])
        setIsLoadingCases(false)
      }
      return
    }
    if (currentRequest !== requestId.current) return
    setIsLoadingCases(false)

    // The API returns newest first, so the bounded lookup covers the most
    // recent work first and any omissions are the least relevant ones.
    const eligible = items.filter(couldHaveDecision)
    const candidates = eligible.slice(0, DECISION_LOOKUP_LIMIT)
    setDecisionCoverage({
      checked: candidates.length,
      checkedIds: candidates.map((item) => item.verification_id),
      eligible: eligible.length,
      skipped: Math.max(0, eligible.length - candidates.length),
      failed: 0,
    })

    if (candidates.length === 0) {
      setDecisions({})
      return
    }

    setIsCalculatingOutcomes(true)
    const results = await Promise.allSettled(
      candidates.map((item) => getDecision(item.verification_id)),
    )
    if (currentRequest !== requestId.current) return

    const outcomeByCase: Record<string, DecisionOutcome> = {}
    let failed = 0
    results.forEach((result, index) => {
      const caseId = candidates[index].verification_id
      if (result.status === 'fulfilled') {
        outcomeByCase[caseId] = result.value.decision
      } else if (!isNotFound(result.reason)) {
        // 404 simply means "no decision recorded yet" - not a failure.
        failed += 1
      }
    })
    setDecisions(outcomeByCase)
    setDecisionCoverage((previous) => ({ ...previous, failed }))
    setIsCalculatingOutcomes(false)
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const counts = useMemo<CaseOverviewCounts>(() => {
    const byStatus: Record<VerificationCase['status'], number> = {
      draft: 0,
      in_progress: 0,
      completed: 0,
      review_required: 0,
      cancelled: 0,
    }
    cases.forEach((item) => {
      byStatus[item.status] = (byStatus[item.status] ?? 0) + 1
    })

    const byOutcome: Record<DecisionOutcome, number> = {
      VERIFIED: 0,
      REVIEW_REQUIRED: 0,
      MISMATCH: 0,
    }
    Object.values(decisions).forEach((outcome) => {
      byOutcome[outcome] += 1
    })

    const decided = Object.keys(decisions).length
    return {
      total: cases.length,
      draft: byStatus.draft,
      inProgress: byStatus.in_progress,
      reviewRequired: byStatus.review_required,
      completed: byStatus.completed,
      cancelled: byStatus.cancelled,
      verified: byOutcome.VERIFIED,
      mismatch: byOutcome.MISMATCH,
      decisionReviewRequired: byOutcome.REVIEW_REQUIRED,
      decided,
      awaitingDecision: Math.max(0, cases.length - decided),
    }
  }, [cases, decisions])

  return {
    cases,
    counts,
    decisions,
    isLoadingCases,
    isCalculatingOutcomes,
    error,
    decisionCoverage,
    refresh: () => void load(),
  }
}
