import type { ConsistencyLevel } from '../types/api'
import { formatConsistency, formatDecision } from '../utils/reportFormat'
import { AlertIcon, CheckCircleIcon, ClockIcon, DotIcon, XIcon } from './Icons'

/**
 * Step 10: consistent visual language for the backend's decision outcomes.
 * The three values come from `models/verification_decision.DecisionOutcome`
 * and are only displayed here - the decision itself is always computed by the
 * deterministic Step 8 engine.
 */
const DECISION_STYLES: Record<string, { className: string; Icon: typeof DotIcon }> = {
  VERIFIED: { className: 'bg-brand-50 text-brand-800 ring-brand-200', Icon: CheckCircleIcon },
  REVIEW_REQUIRED: { className: 'bg-amber-50 text-amber-800 ring-amber-200', Icon: ClockIcon },
  MISMATCH: { className: 'bg-red-50 text-red-800 ring-red-200', Icon: XIcon },
}

const DECISION_NEUTRAL = { className: 'bg-gray-100 text-gray-600 ring-gray-300', Icon: DotIcon }

interface DecisionBadgeProps {
  decision: string | null | undefined
  size?: 'sm' | 'lg'
}

export function DecisionBadge({ decision, size = 'sm' }: DecisionBadgeProps) {
  const style = DECISION_STYLES[decision ?? ''] ?? DECISION_NEUTRAL
  const Icon = style.Icon
  return (
    <span
      className={`gv-badge ${size === 'lg' ? 'px-3 py-1.5 text-sm' : 'px-2.5 py-0.5 text-xs'} ${style.className}`}
    >
      <Icon size={size === 'lg' ? 15 : 13} />
      {formatDecision(decision)}
    </span>
  )
}

/** CONSISTENT / INCONSISTENT / NOT_DETECTED pills used by the evidence block. */
const CONSISTENCY_STYLES: Record<ConsistencyLevel, { className: string; Icon: typeof DotIcon }> = {
  CONSISTENT: { className: 'bg-brand-50 text-brand-800 ring-brand-200', Icon: CheckCircleIcon },
  INCONSISTENT: { className: 'bg-red-50 text-red-800 ring-red-200', Icon: XIcon },
  NOT_DETECTED: { className: 'bg-gray-100 text-gray-600 ring-gray-300', Icon: AlertIcon },
}

export function ConsistencyBadge({ level }: { level: ConsistencyLevel | null | undefined }) {
  const style = CONSISTENCY_STYLES[level ?? 'NOT_DETECTED'] ?? DECISION_NEUTRAL
  const Icon = style.Icon
  return (
    <span className={`gv-badge ${style.className}`}>
      <Icon size={13} />
      {formatConsistency(level).replace(/^[✓×—]\s*/, '')}
    </span>
  )
}
