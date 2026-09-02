import type {
  ComparisonClassification,
  DnaComparisonResponse,
  MarkerStatus,
} from '../types/api'

const CLASSIFICATION_STYLES: Record<ComparisonClassification, string> = {
  EXACT_MATCH: 'border-green-200 bg-green-50 text-green-800',
  PARTIAL_MATCH: 'border-amber-200 bg-amber-50 text-amber-800',
  NO_MATCH: 'border-red-200 bg-red-50 text-red-800',
  INVALID: 'border-gray-200 bg-gray-50 text-gray-700',
}

const CLASSIFICATION_LABELS: Record<ComparisonClassification, string> = {
  EXACT_MATCH: 'STR profile consistent with reference profile',
  PARTIAL_MATCH: 'Partial match — not an identity confirmation',
  NO_MATCH: 'No match',
  INVALID: 'Comparison could not be evaluated',
}

const MARKER_STATUS_STYLES: Record<MarkerStatus, string> = {
  MATCH: 'bg-green-50 text-green-700 ring-green-200',
  MISMATCH: 'bg-red-50 text-red-700 ring-red-200',
  MISSING_REFERENCE: 'bg-amber-50 text-amber-700 ring-amber-200',
  MISSING_SUBMITTED: 'bg-amber-50 text-amber-700 ring-amber-200',
  INVALID: 'bg-gray-100 text-gray-600 ring-gray-300',
}

function formatAlleles(alleles: number[] | null): string {
  if (!alleles) return '—'
  return alleles.map((allele) => Number.isInteger(allele) ? allele : allele.toFixed(1)).join(', ')
}

/**
 * Shared presentation of one deterministic STR comparison result. Used by
 * the manual/test profile section (Step 5) and the AI-extraction flow
 * (Step 7) — the comparison itself is ALWAYS produced server-side by the
 * deterministic STR engine, never by AI.
 */
export default function DnaComparisonResultView({ result }: { result: DnaComparisonResponse }) {
  return (
    <div className="space-y-4">
      <div className={`rounded-lg border px-4 py-3 ${CLASSIFICATION_STYLES[result.classification]}`}>
        <p className="text-xs font-semibold uppercase tracking-wide opacity-70">Overall result</p>
        <p className="mt-0.5 text-sm font-semibold">{CLASSIFICATION_LABELS[result.classification]}</p>
        <p className="mt-1 text-sm">
          Match percentage: <span className="font-semibold">{result.summary.match_percentage.toFixed(1)}%</span>
        </p>
      </div>

      <div className="flex flex-wrap gap-2 text-xs font-medium">
        <span className="rounded-full bg-white px-2.5 py-1 ring-1 ring-gray-200">{result.summary.total_markers} Total</span>
        <span className="rounded-full bg-green-50 px-2.5 py-1 text-green-700 ring-1 ring-green-200">{result.summary.matched} Matched</span>
        <span className="rounded-full bg-red-50 px-2.5 py-1 text-red-700 ring-1 ring-red-200">{result.summary.mismatched} Mismatched</span>
        <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700 ring-1 ring-amber-200">{result.summary.missing} Missing</span>
        {result.summary.invalid > 0 && (
          <span className="rounded-full bg-gray-100 px-2.5 py-1 text-gray-600 ring-1 ring-gray-300">{result.summary.invalid} Invalid</span>
        )}
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-3 py-2">Marker</th>
              <th className="px-3 py-2">Reference</th>
              <th className="px-3 py-2">Submitted</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {result.markers.map((marker) => (
              <tr key={marker.marker}>
                <td className="px-3 py-1.5 font-mono text-xs text-gray-800">{marker.marker}</td>
                <td className="px-3 py-1.5 font-mono text-xs text-gray-600">{formatAlleles(marker.reference_alleles)}</td>
                <td className="px-3 py-1.5 font-mono text-xs text-gray-600">{formatAlleles(marker.submitted_alleles)}</td>
                <td className="px-3 py-1.5">
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${MARKER_STATUS_STYLES[marker.status]}`}>
                    {marker.status.replaceAll('_', ' ')}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-500">
        Prototype notice: this deterministic comparison runs against synthetic
        demonstration data. The match percentage is a marker count ratio — it is
        not a forensic probability and does not constitute legally valid identity
        confirmation. A partial match never confirms identity.
      </p>
    </div>
  )
}
