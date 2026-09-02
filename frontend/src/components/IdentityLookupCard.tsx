import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '../services/apiClient'
import { lookupIdentityByCnic } from '../services/identityService'
import type { IdentityLookupResponse } from '../types/api'

/**
 * Developer/test UI: CNIC input → search → display the returned synthetic
 * identity. Final dashboard design is intentionally out of scope here.
 */
export default function IdentityLookupCard() {
  const [cnic, setCnic] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<IdentityLookupResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const query = cnic.trim()
    if (!query || isLoading) return

    setIsLoading(true)
    setResult(null)
    setError(null)
    try {
      const identity = await lookupIdentityByCnic(query)
      setResult(identity)
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Unexpected error while looking up the identity.',
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
        <label htmlFor="cnic-input" className="sr-only">
          CNIC
        </label>
        <input
          id="cnic-input"
          value={cnic}
          onChange={(event) => setCnic(event.target.value)}
          placeholder="e.g. 99900-0000001-1"
          inputMode="numeric"
          className="w-full flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
        />
        <button
          type="submit"
          disabled={isLoading || cnic.trim().length === 0}
          className="rounded-lg bg-brand-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isLoading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {error && (
        <p className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">
          {error}
        </p>
      )}

      {result && (
        <dl className="mt-5 grid grid-cols-1 gap-x-6 gap-y-3 border-t border-gray-100 pt-5 sm:grid-cols-2">
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Name</dt>
            <dd className="mt-1 text-sm font-medium text-gray-900">{result.name}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">CNIC</dt>
            <dd className="mt-1 text-sm font-medium text-gray-900">{result.cnic}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Father name</dt>
            <dd className="mt-1 text-sm text-gray-900">{result.father_name}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Date of birth</dt>
            <dd className="mt-1 text-sm text-gray-900">{result.date_of_birth}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Gender</dt>
            <dd className="mt-1 text-sm capitalize text-gray-900">{result.gender}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Status</dt>
            <dd className="mt-1 text-sm text-gray-900">{result.status.replace('_', ' ')}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Address</dt>
            <dd className="mt-1 text-sm text-gray-900">{result.address}</dd>
          </div>
        </dl>
      )}

      <p className="mt-5 text-xs text-gray-400">
        The DNA/STR reference profile is intentionally not shown here — it stays internal to the
        verification workflow.
      </p>
    </div>
  )
}
