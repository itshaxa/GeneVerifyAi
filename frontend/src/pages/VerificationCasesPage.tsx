import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import CaseStatusBadge from '../components/CaseStatusBadge'
import { ChevronRightIcon, FolderIcon, PlusIcon } from '../components/Icons'
import { EmptyState, ErrorState, LoadingBlock, ScrollHint } from '../components/StateBlocks'
import { ApiError } from '../services/apiClient'
import { listVerifications } from '../services/verificationService'
import { formatTimestamp } from '../utils/format'
import type { VerificationCase } from '../types/api'

/**
 * Lists the verification cases accessible to the signed-in user
 * (admins additionally see all cases — the backend decides).
 */
export default function VerificationCasesPage() {
  const [cases, setCases] = useState<VerificationCase[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await listVerifications()
      setCases(response.items)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load verification cases.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="mx-auto w-full max-w-5xl">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="gv-eyebrow">My Cases</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
            My verification cases
          </h1>
          <p className="mt-1.5 text-sm text-gray-600">
            Cases you created (administrators additionally see all cases).
          </p>
        </div>
        <Link to="/verify" className="gv-btn gv-btn-primary shrink-0">
          <PlusIcon size={15} />
          New verification
        </Link>
      </header>

      {isLoading && <LoadingBlock label="Loading your cases…" />}

      {!isLoading && error && <ErrorState message={error} onRetry={() => void load()} />}

      {!isLoading && !error && cases && cases.length === 0 && (
        <EmptyState
          icon={<FolderIcon size={18} />}
          title="No verification cases yet"
          description="Start a verification from the workspace to create your first case."
          actionLabel="Open workspace"
          actionHref="/verify"
        />
      )}

      {!isLoading && !error && cases && cases.length > 0 && (
        <div className="gv-card animate-gv-fade-up overflow-hidden">
          <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-left text-xs font-semibold tracking-wide text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3">Verification ID</th>
                <th className="px-4 py-3">Identity</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Updated</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {cases.map((item) => (
                <tr key={item.verification_id} className="transition hover:bg-brand-50/40">
                  <td className="px-4 py-3 font-mono text-xs font-semibold text-gray-900">
                    {item.verification_id}
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    <span className="block capitalize">{item.identity.name}</span>
                    <span className="block text-xs text-gray-400">{item.identity.cnic}</span>
                  </td>
                  <td className="px-4 py-3">
                    <CaseStatusBadge status={item.status} />
                  </td>
                  <td className="px-4 py-3 text-gray-500">{formatTimestamp(item.created_at)}</td>
                  <td className="px-4 py-3 text-gray-500">{formatTimestamp(item.updated_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to={`/verifications/${item.verification_id}`}
                      className="gv-btn gv-btn-sm gv-btn-secondary"
                    >
                      View
                      <ChevronRightIcon size={14} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          <ScrollHint className="px-4 pb-4" />
        </div>
      )}
    </div>
  )
}
