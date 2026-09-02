import { Link } from 'react-router-dom'

import StatusBadge from '../components/StatusBadge'
import type { BackendStatus } from '../components/StatusBadge'
import { ActivityIcon, ArrowRightIcon, ShieldIcon } from '../components/Icons'
import { API_BASE_URL } from '../services/apiClient'
import { useHealthCheck } from '../hooks/useHealthCheck'

/**
 * Project overview — the original landing surface, kept reachable at
 * `/overview` so nothing is lost when the Command Center became the home page.
 *
 * Step 10 replaced the outdated "these features arrive in future stages"
 * wording with the accurate prototype positioning. All eight workflow stages
 * shown here already exist; nothing here advertises unbuilt functionality.
 */
export default function HomePage() {
  const { health, isLoading, error } = useHealthCheck()

  const status: BackendStatus = isLoading ? 'loading' : health ? 'online' : 'offline'

  return (
    <section className="mx-auto w-full max-w-4xl space-y-6">
      <div className="gv-card animate-gv-fade-up overflow-hidden">
        <div className="bg-gradient-to-br from-white via-white to-brand-50/70 px-5 py-8 sm:px-8 sm:py-10">
          <span className="gv-badge bg-brand-50 text-brand-700 ring-brand-200">
            <ShieldIcon size={13} />
            Hackathon Prototype — Synthetic Demonstration Data
          </span>
          <h1 className="mt-4 text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            GeneVerify AI
          </h1>
          <p className="mt-2 text-lg font-medium text-brand-700">
            AI-assisted identity verification
          </p>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-gray-600">
            AI-assisted identity verification using synthetic identity records, document
            intelligence, deterministic STR comparison, evidence scoring, and auditable
            verification reports.
          </p>
          <p className="mt-4 max-w-2xl text-sm font-medium text-gray-700">
            GeneVerify is a prototype and is not a legally valid forensic identity system.
          </p>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/" className="gv-btn gv-btn-primary">
              Open the Command Center
              <ArrowRightIcon size={15} />
            </Link>
            <Link to="/verify" className="gv-btn gv-btn-secondary">
              Start a verification
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-px border-t border-gray-100 bg-gray-100 sm:grid-cols-2">
          <Capability
            title="Deterministic by design"
            body="A fixed 20-marker STR panel and a transparent scoring formula produce every outcome. The same evidence always yields the same decision."
          />
          <Capability
            title="AI never decides"
            body="AI performs document extraction only. Every comparison, evidence score and decision is produced by the deterministic engine."
          />
          <Capability
            title="Fully auditable"
            body="Each case keeps an append-only trail of recorded actions, and the report is assembled from that trail."
          />
          <Capability
            title="Synthetic data only"
            body="123 synthetic identity records and 123 linked DNA profiles. No real personal data is processed anywhere."
          />
        </div>
      </div>

      <div className="gv-card animate-gv-fade-up px-5 py-5 sm:px-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <span
              className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700 ring-1 ring-brand-100"
              aria-hidden="true"
            >
              <ActivityIcon size={16} />
            </span>
            <div>
              <h2 className="gv-section-title">Backend connectivity</h2>
              <p className="mt-1 text-xs text-gray-500">
                Checking{' '}
                <code className="rounded bg-gray-100 px-1 py-0.5 font-mono">{API_BASE_URL}/health</code>
              </p>
            </div>
          </div>
          <StatusBadge status={status} />
        </div>

        {health && (
          <dl className="mt-5 grid grid-cols-1 gap-4 border-t border-gray-100 pt-5 sm:grid-cols-3">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Service</dt>
              <dd className="mt-1 text-sm font-medium text-gray-900">{health.app}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Environment</dt>
              <dd className="mt-1 text-sm font-medium text-gray-900">{health.environment}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Version</dt>
              <dd className="mt-1 text-sm font-medium text-gray-900">{health.version}</dd>
            </div>
          </dl>
        )}

        {error && (
          <p className="mt-5 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">
            {error}
          </p>
        )}
      </div>
    </section>
  )
}

function Capability({ title, body }: { title: string; body: string }) {
  return (
    <div className="min-w-0 bg-white px-5 py-4">
      <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      <p className="mt-1 text-sm leading-relaxed text-gray-600">{body}</p>
    </div>
  )
}
