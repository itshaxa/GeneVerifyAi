export type BackendStatus = 'loading' | 'online' | 'offline'

interface StatusBadgeProps {
  status: BackendStatus
}

const STATUS_CONFIG: Record<BackendStatus, { label: string; className: string; dotClassName: string }> = {
  loading: {
    label: 'Checking API…',
    className: 'bg-gray-100 text-gray-600 ring-gray-200',
    dotClassName: 'bg-gray-400',
  },
  online: {
    label: 'API online',
    className: 'bg-brand-50 text-brand-700 ring-brand-200',
    dotClassName: 'bg-brand-500',
  },
  offline: {
    label: 'API unreachable',
    className: 'bg-red-50 text-red-700 ring-red-200',
    dotClassName: 'bg-red-500',
  },
}

/** Small pill indicating backend reachability. */
export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status]
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ring-1 ${config.className}`}
    >
      <span className={`h-2 w-2 rounded-full ${config.dotClassName}`} aria-hidden="true" />
      {config.label}
    </span>
  )
}
