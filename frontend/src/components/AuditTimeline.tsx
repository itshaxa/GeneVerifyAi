/**
 * Step 9: audit timeline — clean vertical activity history of one case.
 * Step 10: same data, clearer presentation (icon per event type, separated
 * actor / raw-code lines, staggered entrance).
 *
 * Purely presentational: it renders exactly what the backend audit trail
 * contains (timestamp, event, actor) and adds nothing. Events come from the
 * append-only `verification_audit_events` table through the report API, so
 * the list is always the recorded history, never a client-side reconstruction.
 */

import type { AuditEventType, ReportAuditEvent } from '../types/api'
import { formatTimestamp } from '../utils/format'
import { auditEventLabel } from '../utils/reportFormat'
import {
  CompareIcon,
  FileTextIcon,
  GavelIcon,
  PlusIcon,
  SparklesIcon,
  UploadIcon,
} from './Icons'

interface Props {
  events: ReportAuditEvent[]
  /** Empty-state message when a case has no recorded events yet. */
  emptyMessage?: string
}

/** One recognisable glyph per recorded event type (display only). */
const EVENT_ICONS: Record<AuditEventType, typeof PlusIcon> = {
  CASE_CREATED: PlusIcon,
  DOCUMENT_UPLOADED: UploadIcon,
  DOCUMENT_PROCESSED: SparklesIcon,
  DNA_COMPARED: CompareIcon,
  DECISION_GENERATED: GavelIcon,
  REPORT_GENERATED: FileTextIcon,
}

export default function AuditTimeline({
  events,
  emptyMessage = 'No audit events recorded.',
}: Props) {
  if (events.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-gray-300 bg-gray-50/60 px-4 py-6 text-center text-sm text-gray-500">
        {emptyMessage}
      </p>
    )
  }

  return (
    <ol className="relative">
      {events.map((event, index) => {
        const Icon = EVENT_ICONS[event.event_type] ?? PlusIcon
        const isLast = index === events.length - 1
        return (
          <li
            key={`${event.event_type}-${index}`}
            className="relative flex animate-gv-fade-up gap-3 pb-5 last:pb-0"
          >
            {!isLast && (
              <span
                className="absolute top-9 bottom-0 left-[15px] w-px bg-gray-200"
                aria-hidden="true"
              />
            )}
            <span
              className="relative mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-700 ring-1 ring-brand-200"
              aria-hidden="true"
            >
              <Icon size={15} />
            </span>

            <div className="min-w-0 flex-1 pb-1">
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <p className="text-sm font-semibold text-gray-900">{auditEventLabel(event)}</p>
                <p className="text-xs text-gray-500">{formatTimestamp(event.timestamp)}</p>
              </div>
              {event.description && (
                <p className="mt-0.5 text-sm leading-relaxed break-words text-gray-600">
                  {event.description}
                </p>
              )}
              <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-400">
                <span>
                  Actor: <span className="font-medium text-gray-600">{event.actor}</span>
                </span>
                <span
                  className="font-mono text-[11px] font-medium tracking-wide text-gray-500 uppercase"
                  title="Raw audit event code stored by the backend"
                >
                  {event.event_type}
                </span>
              </div>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
