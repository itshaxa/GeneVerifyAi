/**
 * Step 10: GeneVerify Command Center - the authenticated landing screen.
 *
 * Everything on this page is read through existing APIs: case status counts
 * come from `GET /verifications`, decision outcomes from
 * `GET /verifications/{id}/decision`, backend reachability from
 * `GET /health`. There is no aggregate-statistics endpoint, so where a number
 * could not be counted from real records the page says so instead of showing
 * an invented figure (see `hooks/useCaseOverview.ts`).
 */

import { Link } from 'react-router-dom'

import CaseStatusBadge from '../components/CaseStatusBadge'
import { DecisionBadge } from '../components/DecisionBadge'
import {
  ActivityIcon,
  AlertIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  ClockIcon,
  FolderIcon,
  LogoutIcon,
  PlusIcon,
  RefreshIcon,
  ShieldIcon,
} from '../components/Icons'
import QuickActions from '../components/QuickActions'
import { EmptyState, ErrorState, Skeleton } from '../components/StateBlocks'
import VerificationPipeline from '../components/VerificationPipeline'
import { useAuth } from '../context/AuthContext'
import { useCaseOverview } from '../hooks/useCaseOverview'
import { useHealthCheck } from '../hooks/useHealthCheck'
import { API_BASE_URL } from '../services/apiClient'
import { formatRelative } from '../utils/format'

export default function DashboardPage() {
  const { user, logout } = useAuth()
  const { health, isLoading: healthLoading, error: healthError } = useHealthCheck()
  const {
    cases,
    counts,
    decisions,
    isLoadingCases,
    isCalculatingOutcomes,
    error,
    decisionCoverage,
    refresh,
  } = useCaseOverview()

  const backendOnline = health?.status === 'ok'
  const healthLabel = healthLoading ? 'Checking API…' : backendOnline ? 'API online' : 'API unreachable'

  return (
    <div className="flex flex-col gap-6 sm:gap-8">
      {/* Hero ------------------------------------------------------------- */}
      <section className="gv-card animate-gv-fade-up relative overflow-hidden">
        <div
          className="pointer-events-none absolute -top-24 -right-16 h-64 w-64 rounded-full bg-brand-100/50 blur-3xl"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute -bottom-24 -left-10 h-56 w-56 rounded-full bg-sky-100/40 blur-3xl"
          aria-hidden="true"
        />
        <div className="relative flex flex-col gap-6 p-6 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="gv-eyebrow flex items-center gap-2">
                <ShieldIcon size={13} />
                Command Center
              </p>
              {/* One heading so assistive tech reads the full product title. */}
              <h1 className="mt-1.5 text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
                GeneVerify AI
                <span className="mt-1 block text-sm font-medium text-brand-700 sm:text-base">
                  AI-Powered Identity Verification
                </span>
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-relaxed text-gray-600">
                AI-assisted identity verification using synthetic identity records, document
                intelligence, deterministic STR comparison, evidence scoring, and auditable
                verification reports.
              </p>
            </div>
            <div className="flex flex-col items-start gap-2 sm:items-end">
              {/* Wraps on very narrow screens instead of being clipped. */}
              <span className="gv-badge max-w-full whitespace-normal bg-brand-50 text-brand-800 ring-brand-200">
                <ActivityIcon size={13} />
                Hackathon Prototype — Synthetic Demonstration Data
              </span>
              <span
                className={`gv-badge ${
                  backendOnline
                    ? 'bg-gray-50 text-gray-600 ring-gray-200'
                    : 'bg-red-50 text-red-700 ring-red-200'
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${backendOnline ? 'animate-gv-ping bg-brand-500' : 'bg-red-500'}`}
                  aria-hidden="true"
                />
                {healthLabel}
              </span>
            </div>
          </div>

          {/* User strip: username, role, logout (Step 10 requirement 1). */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 pt-5">
            <div className="flex items-center gap-3">
              <span
                className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-sm font-bold text-white shadow-sm"
                aria-hidden="true"
              >
                {(user?.username ?? 'G').slice(0, 2).toUpperCase()}
              </span>
              <div className="leading-tight">
                <p className="text-sm text-gray-500">
                  Signed in as <span className="font-semibold text-gray-900">{user?.username}</span>
                </p>
                <p className="gv-eyebrow mt-0.5">{user?.role}</p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={refresh}
                disabled={isLoadingCases}
                className="gv-btn gv-btn-secondary"
              >
                <RefreshIcon size={15} />
                {isLoadingCases ? 'Refreshing…' : 'Refresh'}
              </button>
              <Link to="/verify" className="gv-btn gv-btn-primary">
                <PlusIcon size={15} />
                Start Verification
              </Link>
              <button type="button" onClick={() => void logout()} className="gv-btn gv-btn-ghost">
                <LogoutIcon size={15} />
                Log out
              </button>
            </div>
          </div>
        </div>
      </section>

      {error && <ErrorState message={error} onRetry={refresh} retryLabel="Retry" />}

      {/* Overview cards --------------------------------------------------- */}
      <section aria-labelledby="overview-heading">
        <div className="mb-3 flex items-center gap-2">
          <span className="text-brand-600" aria-hidden="true">
            <FolderIcon size={15} />
          </span>
          <h2 id="overview-heading" className="gv-eyebrow">
            Overview
          </h2>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Verification Cases"
            value={counts.total}
            isLoading={isLoadingCases}
            hint={`${counts.draft} draft · ${counts.inProgress} in progress`}
            tone="neutral"
            Icon={FolderIcon}
          />
          <StatCard
            label="Review Required"
            value={counts.decisionReviewRequired}
            isLoading={isLoadingCases}
            isCounting={isCalculatingOutcomes}
            hint="Decision recorded as REVIEW_REQUIRED"
            tone="amber"
            Icon={ClockIcon}
          />
          <StatCard
            label="Verified"
            value={counts.verified}
            isLoading={isLoadingCases}
            isCounting={isCalculatingOutcomes}
            hint="Decision recorded as VERIFIED"
            tone="brand"
            Icon={CheckCircleIcon}
          />
          <StatCard
            label="Mismatch"
            value={counts.mismatch}
            isLoading={isLoadingCases}
            isCounting={isCalculatingOutcomes}
            hint="Decision recorded as MISMATCH"
            tone="red"
            Icon={AlertIcon}
          />
        </div>
        <p className="mt-2 text-xs leading-relaxed text-gray-500">
          {isLoadingCases
            ? 'Counting your accessible cases…'
            : describeDecisionBasis(counts.total, decisionCoverage, isCalculatingOutcomes)}
        </p>
      </section>

      {/* Quick actions ---------------------------------------------------- */}
      <QuickActions />

      {/* Pipeline --------------------------------------------------------- */}
      <section className="gv-card animate-gv-fade-up overflow-hidden">
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 bg-gray-50/60 px-5 py-4">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-700 ring-1 ring-brand-100">
              <ActivityIcon size={16} />
            </span>
            <div>
              <p className="gv-eyebrow">Workflow</p>
              <h2 className="gv-section-title mt-0.5">Verification Pipeline</h2>
              <p className="mt-1 text-sm text-gray-500">
                Every case moves through the same eight stages, each one recorded in the audit trail.
              </p>
            </div>
          </div>
          <Link
            to="/verify"
            className="gv-btn gv-btn-ghost self-center text-brand-700 hover:bg-brand-50"
          >
            Run a verification
            <ArrowRightIcon size={15} />
          </Link>
        </header>
        <div className="p-5 sm:p-6">
          <VerificationPipeline variant="reference" />
        </div>
      </section>

      {/* Recent cases ----------------------------------------------------- */}
      <section className="gv-card animate-gv-fade-up overflow-hidden">
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 bg-gray-50/60 px-5 py-4">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-700 ring-1 ring-brand-100">
              <ClockIcon size={16} />
            </span>
            <div>
              <p className="gv-eyebrow">Latest activity</p>
              <h2 className="gv-section-title mt-0.5">Recent Verification Cases</h2>
            </div>
          </div>
          <Link to="/verifications" className="gv-btn gv-btn-ghost self-center text-brand-700 hover:bg-brand-50">
            All cases
            <ArrowRightIcon size={15} />
          </Link>
        </header>

        <div className="p-5 sm:p-6">
          {isLoadingCases ? (
            <ul className="flex flex-col gap-2" aria-busy="true">
              {[0, 1, 2].map((row) => (
                <li key={row} className="flex items-center gap-3 rounded-xl border border-gray-100 p-3">
                  <Skeleton className="h-9 w-9 rounded-lg" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-3 w-40" />
                    <Skeleton className="h-3 w-24" />
                  </div>
                  <Skeleton className="h-6 w-24 rounded-full" />
                </li>
              ))}
            </ul>
          ) : cases.length === 0 ? (
            <EmptyState
              title="No verification cases yet"
              description="Start by looking up a CNIC — GeneVerify will open a case you can attach a blood or DNA test document to."
              actionLabel="Start Verification"
              actionHref="/verify"
              icon={<FolderIcon size={18} />}
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {cases.slice(0, 5).map((item) => (
                <li key={item.verification_id}>
                  <Link
                    to={`/verifications/${item.verification_id}`}
                    className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-gray-200 p-3 transition duration-200 ease-out hover:border-brand-300 hover:bg-brand-50/40"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-mono text-sm font-semibold text-gray-900">
                        {item.verification_id}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-gray-500">
                        {item.identity.name} · {item.identity.cnic}
                      </p>
                    </div>
                    <p className="w-full text-xs text-gray-400 sm:w-auto">
                      {formatRelative(item.created_at)}
                    </p>
                    <div className="flex items-center gap-2">
                      {decisions[item.verification_id] && (
                        <DecisionBadge decision={decisions[item.verification_id]} />
                      )}
                      <CaseStatusBadge status={item.status} />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {/* System panel (the old home page's health check, kept honest) ------ */}
      <section className="gv-card animate-gv-fade-up p-5 sm:p-6">
        <h2 className="gv-section-title">System Status</h2>
        <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="min-w-0">
            <dt className="gv-eyebrow">Backend</dt>
            <dd className="mt-1 text-sm font-medium break-all text-gray-900">
              {healthError ? 'Unreachable' : health ? `${health.app} ${health.version}` : 'Checking…'}
            </dd>
          </div>
          <div className="min-w-0">
            <dt className="gv-eyebrow">Environment</dt>
            <dd className="mt-1 text-sm font-medium text-gray-900">{health?.environment ?? '—'}</dd>
          </div>
          <div className="min-w-0">
            <dt className="gv-eyebrow">API endpoint</dt>
            <dd className="mt-1 font-mono text-xs break-all text-gray-600">{API_BASE_URL}</dd>
          </div>
          <div className="min-w-0">
            <dt className="gv-eyebrow">Signed in</dt>
            <dd className="mt-1 text-sm font-medium text-gray-900">{user?.username ?? '—'}</dd>
          </div>
        </dl>
        <p className="mt-5 border-t border-gray-100 pt-4 text-xs leading-relaxed text-gray-500">
          GeneVerify is a prototype and is not a legally valid forensic identity system. All identity
          records, DNA profiles and documents in this demonstration are synthetic.
        </p>
      </section>
    </div>
  )
}

/* ---------------------------------------------------------------------- */

const TONE_STYLES = {
  neutral: 'bg-gray-100 text-gray-700 ring-gray-200',
  brand: 'bg-brand-50 text-brand-700 ring-brand-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  red: 'bg-red-50 text-red-700 ring-red-200',
} as const

interface StatCardProps {
  label: string
  value: number
  hint: string
  tone: keyof typeof TONE_STYLES
  Icon: typeof FolderIcon
  isLoading?: boolean
  /** Slows the number down while decisions are still being read. */
  isCounting?: boolean
}

function StatCard({ label, value, hint, tone, Icon, isLoading, isCounting }: StatCardProps) {
  return (
    <div className="gv-card gv-card-hover animate-gv-fade-up flex min-w-0 flex-col justify-between p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="gv-eyebrow">{label}</p>
        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ring-1 ${TONE_STYLES[tone]}`}>
          <Icon size={15} />
        </span>
      </div>
      <p className="mt-3 flex items-baseline gap-2">
        {isLoading ? (
          <Skeleton className="h-8 w-14" />
        ) : (
          <span className="text-3xl font-bold tracking-tight text-gray-900 tabular-nums">{value}</span>
        )}
        {isCounting && !isLoading && <span className="text-xs text-gray-400">counting…</span>}
      </p>
      <p className="mt-1 text-xs leading-relaxed text-gray-500">{hint}</p>
    </div>
  )
}

/**
 * States exactly what the decision numbers are based on. The backend has no
 * aggregate endpoint, so this line is the honesty requirement in words.
 */
function describeDecisionBasis(
  total: number,
  coverage: { checked: number; eligible: number; skipped: number; failed: number },
  isCalculating: boolean,
): string {
  if (isCalculating) return 'Reading the recorded decision of each case…'
  if (total === 0) return 'Figures appear once you have verification cases.'
  if (coverage.eligible === 0) {
    return 'Verified and Mismatch stay at zero until a case has an evidence assessment recorded.'
  }
  const parts = [
    coverage.skipped > 0
      ? `Verified and Mismatch are counted from the ${coverage.checked} most recent cases that can hold a decision; ${coverage.skipped} older ones are not counted.`
      : `Verified and Mismatch are counted from the decision stored on each of your ${coverage.eligible} assessable cases.`,
  ]
  if (coverage.failed > 0) {
    parts.push(`${coverage.failed} case(s) could not be read, so the totals may be lower than reality.`)
  }
  return parts.join(' ')
}
