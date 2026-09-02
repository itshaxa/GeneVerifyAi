/**
 * Shared display formatting for the Step 9 report views.
 *
 * Presentation only: no scoring, no decisions, no interpretation of DNA.
 * The event labels below mirror `AUDIT_EVENT_LABELS` in
 * `backend/app/models/verification_audit.py`, which is also where the API
 * gets the `event` text of every timeline entry - the backend stays the
 * single source of truth and these labels are only a display fallback.
 */

import type { AuditEventType, ReportAuditEvent } from '../types/api'

export const AUDIT_EVENT_LABELS: Record<AuditEventType, string> = {
  CASE_CREATED: 'Case created',
  DOCUMENT_UPLOADED: 'Document uploaded',
  DOCUMENT_PROCESSED: 'AI extraction completed',
  DNA_COMPARED: 'DNA comparison completed',
  DECISION_GENERATED: 'Verification decision generated',
  REPORT_GENERATED: 'Report generated',
}

/** Human label of an audit event (backend label wins when present). */
export function auditEventLabel(event: ReportAuditEvent): string {
  return event.event || AUDIT_EVENT_LABELS[event.event_type] || event.event_type
}

/** Code words that stay uppercase when humanized (matches the PDF renderer). */
const ACRONYMS = new Set(['dna', 'cnic', 'str', 'ai', 'id', 'pdf'])

/** 'REVIEW_REQUIRED' -> 'Review required', 'DNA_REPORT' -> 'DNA report'. */
export function humanizeCode(value: string | null | undefined): string {
  if (!value) return ''
  const text = value
    .toLowerCase()
    .split('_')
    .map((word) => (ACRONYMS.has(word) ? word.toUpperCase() : word))
    .join(' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function formatDecision(value: string | null | undefined): string {
  switch (value) {
    case 'VERIFIED':
      return 'VERIFIED'
    case 'REVIEW_REQUIRED':
      return 'REVIEW REQUIRED'
    case 'MISMATCH':
      return 'MISMATCH'
    default:
      return value ?? 'No decision'
  }
}

export function formatClassification(value: string | null | undefined): string {
  switch (value) {
    case 'EXACT_MATCH':
      return 'EXACT MATCH'
    case 'PARTIAL_MATCH':
      return 'PARTIAL MATCH'
    case 'NO_MATCH':
      return 'NO MATCH'
    case 'INVALID':
      return 'INVALID'
    default:
      return value ?? 'Not available'
  }
}

/** Consistency levels keep the Step 8 visual language (✓ / × / —). */
export function formatConsistency(value: string | null | undefined): string {
  switch (value) {
    case 'CONSISTENT':
      return '✓ CONSISTENT'
    case 'INCONSISTENT':
      return '× INCONSISTENT'
    case 'NOT_DETECTED':
      return '— Not detected'
    default:
      return value ?? '— Not available'
  }
}

export function formatPercent(value: number | null | undefined): string {
  return value == null ? '—' : `${value.toFixed(1)}%`
}

export function formatFileSize(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

/** Banner classes matching the Step 8 decision card. */
export function decisionBannerClasses(value: string | null | undefined): string {
  switch (value) {
    case 'VERIFIED':
      return 'bg-green-50 text-green-800'
    case 'REVIEW_REQUIRED':
      return 'bg-amber-50 text-amber-800'
    case 'MISMATCH':
      return 'bg-red-50 text-red-800'
    default:
      return 'bg-gray-50 text-gray-800'
  }
}

export function decisionIcon(value: string | null | undefined): string {
  switch (value) {
    case 'VERIFIED':
      return '✓'
    case 'REVIEW_REQUIRED':
      return '!'
    case 'MISMATCH':
      return '×'
    default:
      return '?'
  }
}
