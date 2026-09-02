import { useState } from 'react'

import DnaComparisonResultView from './DnaComparisonResultView'
import DNAHelixAnimation from './DNAHelixAnimation'
import { CompareIcon } from './Icons'
import { ApiError } from '../services/apiClient'
import { compareDna } from '../services/dnaService'
import type { DnaComparisonResponse } from '../types/api'

/**
 * Canonical demonstration STR panel (marker names only — the reference
 * alleles themselves are never sent to or known by the frontend).
 */
export const STR_PANEL_MARKERS = [
  'D3S1358', 'vWA', 'FGA', 'D8S1179', 'D21S11',
  'D18S51', 'D5S818', 'D13S317', 'D7S820', 'CSF1PO',
  'TH01', 'TPOX', 'D16S539', 'D2S1338', 'D19S433',
  'D12S391', 'D10S1248', 'D1S1656', 'D22S1045', 'SE33',
] as const

function buildTemplate(): string {
  const entries = STR_PANEL_MARKERS.map((marker) => `  "${marker}": [0, 0]`).join(',\n')
  return `{\n${entries}\n}`
}

/**
 * Simple prototype DNA Analysis section: structured STR profile input and
 * the deterministic comparison outcome. No uploads or AI in this stage.
 * ``onCompared`` lets the parent refresh case data (a comparison moves a
 * draft case to in_progress server-side).
 */
export default function DnaAnalysisSection({
  verificationId,
  onCompared,
}: {
  verificationId: string
  onCompared?: () => void
}) {
  const [profileText, setProfileText] = useState(buildTemplate())
  const [isComparing, setIsComparing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<DnaComparisonResponse | null>(null)

  const handleCompare = async () => {
    setError(null)
    let parsed: unknown
    try {
      parsed = JSON.parse(profileText)
    } catch {
      setError('The submitted profile is not valid JSON.')
      return
    }

    setIsComparing(true)
    try {
      setResult(await compareDna(verificationId, parsed))
      onCompared?.()
    } catch (err) {
      setResult(null)
      setError(err instanceof ApiError ? err.message : 'DNA comparison failed.')
    } finally {
      setIsComparing(false)
    }
  }

  return (
    <section className="gv-card animate-gv-fade-up overflow-hidden">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 bg-gray-50/60 px-5 py-4">
        <div className="flex items-start gap-3">
          <span
            className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700 ring-1 ring-brand-100"
            aria-hidden="true"
          >
            <CompareIcon size={16} />
          </span>
          <div>
            <p className="gv-eyebrow">Stage 05 · STR Comparison</p>
            <h2 className="gv-section-title mt-0.5">DNA Analysis — manual / test STR profile</h2>
          </div>
        </div>
        <span className="gv-badge bg-gray-100 text-gray-600 ring-gray-300">Prototype test tool</span>
      </header>
      <div className="p-5 sm:p-6">
      <p className="text-sm text-gray-500">
        Structured marker input kept for prototype testing alongside the AI
        document extraction above. The reference profile is resolved by the
        server from the linked identity and can never be supplied by the client.
      </p>

      <label
        htmlFor="submitted-profile"
        className="gv-eyebrow mt-4 block"
      >
        Submitted STR profile (JSON)
      </label>
      <textarea
        id="submitted-profile"
        value={profileText}
        onChange={(event) => setProfileText(event.target.value)}
        rows={8}
        spellCheck={false}
        className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 font-mono text-xs text-gray-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
      />

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => void handleCompare()}
          disabled={isComparing}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isComparing ? 'Comparing…' : 'Compare DNA'}
        </button>
        <button
          type="button"
          onClick={() => setProfileText(buildTemplate())}
          disabled={isComparing}
          className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Reset marker template
        </button>
      </div>

      {error && (
        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}

      <DNAHelixAnimation active={isComparing} className="mt-2 h-36 w-full sm:h-44" />

      {result && (
        <div className="mt-4">
          <DnaComparisonResultView result={result} />
        </div>
      )}
      </div>
    </section>
  )
}
