import type { CaseStatus } from '../types/api'
import { AlertIcon, CheckCircleIcon, ClockIcon, DotIcon, XIcon } from './Icons'

/**
 * Step 10: the single visual language for case status. Enum values are the
 * backend's (`models/verification_case.CaseStatus`) and are never renamed
 * here - only displayed.
 */
const STATUS_STYLES: Record<CaseStatus, { label: string; className: string; Icon: typeof DotIcon }> = {
  draft: {
    label: 'Draft',
    className: 'bg-gray-100 text-gray-600 ring-gray-300',
    Icon: DotIcon,
  },
  in_progress: {
    label: 'In progress',
    className: 'bg-sky-50 text-sky-700 ring-sky-200',
    Icon: ClockIcon,
  },
  completed: {
    label: 'Completed',
    className: 'bg-brand-50 text-brand-700 ring-brand-200',
    Icon: CheckCircleIcon,
  },
  review_required: {
    label: 'Review required',
    className: 'bg-amber-50 text-amber-700 ring-amber-200',
    Icon: AlertIcon,
  },
  cancelled: {
    label: 'Cancelled',
    className: 'bg-red-50 text-red-700 ring-red-200',
    Icon: XIcon,
  },
}

interface Props {
  status: CaseStatus
  /** 'lg' is used by the case header; 'sm' fits table rows. */
  size?: 'sm' | 'lg'
}

/** Compact pill for a verification case status, icon + label. */
export default function CaseStatusBadge({ status, size = 'sm' }: Props) {
  const config = STATUS_STYLES[status] ?? STATUS_STYLES.draft
  const Icon = config.Icon
  return (
    <span
      className={`gv-badge ${
        size === 'lg' ? 'px-3 py-1.5 text-sm' : 'px-2.5 py-0.5 text-xs'
      } ${config.className}`}
    >
      <Icon size={size === 'lg' ? 15 : 13} />
      {config.label}
    </span>
  )
}
