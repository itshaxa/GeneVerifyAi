/**
 * Step 10: the Reports screen reached from the navigation and Quick Actions.
 *
 * There is no report-specific endpoint beyond the Step 9 API, and this page
 * does not invent one: it lists the cases whose report can be opened, and each
 * row links to the existing report view / PDF download. A report of an
 * incomplete case is still available and marks its missing sections itself -
 * that honesty is the backend's, not something assembled here.
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import CaseStatusBadge from '../components/CaseStatusBadge'
import { DecisionBadge } from '../components/DecisionBadge'
import { DownloadIcon, FileTextIcon, InboxIcon, SearchIcon } from '../components/Icons'
import { EmptyState, ErrorState, LoadingBlock, ScrollHint } from '../components/StateBlocks'
import { useCaseOverview } from '../hooks/useCaseOverview'
import { saveReportPdf } from '../services/reportService'
import type { VerificationCase } from '../types/api'
import { describeError } from '../utils/errorMessage'
import { formatDate } from '../utils/format'

type FilterKey = 'all' | 'ready' | 'awaiting'

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'All cases' },
  { key: 'ready', label: 'Decision recorded' },
  { key: 'awaiting', label: 'Awaiting assessment' },
]

export default function ReportsPage() {
  const { cases, decisions, isLoadingCases, isCalculatingOutcomes, error, decisionCoverage, refresh } =
    useCaseOverview()
  const [filter, setFilter] = useState<FilterKey>('all')
  const [query, setQuery] = useState('')
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return cases.filter((item) => {
      const hasDecision = Boolean(decisions[item.verification_id])
      if (filter === 'ready' && !hasDecision) return false
      if (filter === 'awaiting' && hasDecision) return false
      if (!needle) return true
      return (
        item.verification_id.toLowerCase().includes(needle) ||
        item.identity.name.toLowerCase().includes(needle) ||
        item.identity.cnic.toLowerCase().includes(needle)
      )
    })
  }, [cases, decisions, filter, query])

  async function handleDownload(item: VerificationCase) {
    setDownloadingId(item.verification_id)
    setDownloadError(null)
    try {
      await saveReportPdf(item.verification_id)
    } catch (err) {
      setDownloadError(describeError(err, `Unable to generate the report for ${item.verification_id}.`))
    } finally {
      setDownloadingId(null)
    }
  }

  /** Distinguishes "no decision exists" from "not checked" (bounded lookups). */
  function decisionStateOf(item: VerificationCase): 'decided' | 'none' | 'unchecked' {
    if (decisions[item.verification_id]) return 'decided'
    if (item.status === 'draft' || item.status === 'cancelled') return 'none'
    return decisionCoverage.checkedIds.includes(item.verification_id) ? 'none' : 'unchecked'
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="gv-eyebrow">Reports</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
            Verification Reports
          </h1>
          <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-gray-600">
            Every case you can access has an auditable report. Sections that were never completed are
            marked as unavailable in the report itself rather than filled in.
          </p>
        </div>
        <Link to="/verify" className="gv-btn gv-btn-primary shrink-0">
          <FileTextIcon size={15} />
          New verification
        </Link>
      </header>

      {downloadError && <ErrorState message={downloadError} />}

      <section className="gv-card animate-gv-fade-up overflow-hidden">
        <header className="flex flex-col gap-3 border-b border-gray-100 bg-gray-50/60 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <div
            className="flex flex-wrap items-center gap-1.5"
            role="group"
            aria-label="Filter reports by assessment state"
          >
            {FILTERS.map((entry) => (
              <button
                key={entry.key}
                type="button"
                aria-pressed={filter === entry.key}
                onClick={() => setFilter(entry.key)}
                className={`gv-btn gv-btn-sm ${
                  filter === entry.key
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'border border-gray-300 bg-white text-gray-600 hover:border-brand-300 hover:text-brand-700'
                }`}
              >
                {entry.label}
              </button>
            ))}
          </div>
          <div className="relative sm:w-72">
            <label htmlFor="report-search" className="sr-only">
              Search reports by verification ID, name or CNIC
            </label>
            <span
              className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-gray-400"
              aria-hidden="true"
            >
              <SearchIcon size={15} />
            </span>
            <input
              id="report-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search ID, name or CNIC"
              className="w-full rounded-lg border border-gray-300 bg-white py-2 pr-3 pl-9 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200 focus:outline-none"
            />
          </div>
        </header>

        {isLoadingCases ? (
          <LoadingBlock label="Loading your reports…" />
        ) : error ? (
          <div className="p-5">
            <ErrorState message={error} onRetry={refresh} />
          </div>
        ) : visible.length === 0 ? (
          <div className="p-5 sm:p-6">
            <EmptyState
              icon={<InboxIcon size={18} />}
              title={cases.length === 0 ? 'No reports yet' : 'No reports match this filter'}
              description={
                cases.length === 0
                  ? 'Create a verification case to get an auditable report.'
                  : 'Try a different filter or clear the search field.'
              }
              actionLabel={cases.length === 0 ? 'Start Verification' : undefined}
              actionHref={cases.length === 0 ? '/verify' : undefined}
            />
          </div>
        ) : (
          <>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <caption className="sr-only">
                Verification reports accessible to the signed-in user
              </caption>
              <thead className="bg-gray-50 text-left text-xs font-semibold tracking-wide text-gray-500 uppercase">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    Verification ID
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Identity
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Status
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Decision
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Created
                  </th>
                  <th scope="col" className="px-4 py-3 text-right">
                    Report
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {visible.map((item) => {
                  const state = decisionStateOf(item)
                  return (
                    <tr key={item.verification_id} className="transition hover:bg-brand-50/40">
                      <td className="px-4 py-3 font-mono text-xs font-semibold whitespace-nowrap text-gray-900">
                        <Link to={`/verifications/${item.verification_id}`} className="hover:underline">
                          {item.verification_id}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-gray-700">
                        <span className="block max-w-[14rem] truncate">{item.identity.name}</span>
                        <span className="block font-mono text-xs text-gray-400">{item.identity.cnic}</span>
                      </td>
                      <td className="px-4 py-3">
                        <CaseStatusBadge status={item.status} />
                      </td>
                      <td className="px-4 py-3">
                        {state === 'decided' ? (
                          <DecisionBadge decision={decisions[item.verification_id]} />
                        ) : state === 'unchecked' ? (
                          <span className="text-xs text-gray-400">Not checked</span>
                        ) : (
                          <span className="text-xs text-gray-400">No decision yet</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs whitespace-nowrap text-gray-500">
                        {formatDate(item.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-2">
                          <Link
                            to={`/verifications/${item.verification_id}/report`}
                            className="gv-btn gv-btn-sm gv-btn-secondary"
                          >
                            <FileTextIcon size={14} />
                            View
                          </Link>
                          <button
                            type="button"
                            onClick={() => void handleDownload(item)}
                            disabled={downloadingId === item.verification_id}
                            className="gv-btn gv-btn-sm gv-btn-primary"
                          >
                            <DownloadIcon size={14} />
                            {downloadingId === item.verification_id ? 'Generating…' : 'PDF'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <ScrollHint className="px-5 pb-4" />
          </>
        )}

        {!isLoadingCases && !error && visible.length > 0 && (
          <footer className="border-t border-gray-100 bg-gray-50/60 px-5 py-3 text-xs leading-relaxed text-gray-500">
            {isCalculatingOutcomes
              ? 'Reading recorded decisions…'
              : `${visible.length} of ${cases.length} cases shown. `}
            {!isCalculatingOutcomes && decisionCoverage.skipped > 0 && (
              <>
                Decisions were read for the {decisionCoverage.checked} most recent assessable cases;{' '}
                {decisionCoverage.skipped} older ones are shown as “Not checked” rather than guessed.{' '}
              </>
            )}
            Generating a PDF records a REPORT_GENERATED event in that case's audit trail.
          </footer>
        )}
      </section>
    </div>
  )
}
