/**
 * The API returns naive UTC timestamps (the database column default is
 * `CURRENT_TIMESTAMP`). Read verbatim, JavaScript treats them as *local* time,
 * which shifts every displayed instant by the UTC offset and makes an absolute
 * timestamp contradict its own "x min ago" counterpart. A UTC designator is
 * therefore added whenever the value carries none.
 */
function parseTimestamp(iso: string): Date {
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso) ? iso : `${iso}Z`
  return new Date(normalized)
}

/**
 * Format an ISO timestamp from the API for compact display, in the operator's
 * local time resolved from the UTC instant the server recorded.
 */
export function formatTimestamp(iso: string): string {
  const parsed = parseTimestamp(iso)
  if (Number.isNaN(parsed.getTime())) {
    return iso
  }
  return parsed.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

/** Compact date for dashboards and table rows: '28 Aug 2026'. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const parsed = parseTimestamp(iso)
  if (Number.isNaN(parsed.getTime())) return iso
  return parsed.toLocaleDateString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

/**
 * Relative age for the recent-activity list. Falls back to the absolute date
 * beyond a week so nothing is ever presented more precisely than it is.
 */
export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '—'
  const parsed = parseTimestamp(iso)
  if (Number.isNaN(parsed.getTime())) return iso
  const seconds = Math.round((Date.now() - parsed.getTime()) / 1000)
  if (seconds < 0) return 'scheduled'
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days <= 7) return `${days} d ago`
  return formatDate(iso)
}

/**
 * Insert CNIC masking (#####-#######-#) while typing.
 *
 * Presentation only: the backend's `normalize_cnic` still decides what is a
 * valid CNIC, and every request sends exactly what the user typed.
 */
export function formatCnic(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 13)
  if (digits.length <= 5) return digits
  if (digits.length <= 12) return `${digits.slice(0, 5)}-${digits.slice(5)}`
  return `${digits.slice(0, 5)}-${digits.slice(5, 12)}-${digits.slice(12)}`
}

/** Digits only - the length check the CNIC input uses for its feedback. */
export function cnicDigitCount(value: string): number {
  return value.replace(/\D/g, '').length
}
