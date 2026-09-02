import IdentityLookupCard from '../components/IdentityLookupCard'

/**
 * Developer/test page proving frontend -> CNIC lookup endpoint connectivity.
 * Kept reachable from the app footer; the Command Center is the real home.
 */
export default function IdentityLookupPage() {
  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight text-gray-900">CNIC identity lookup</h1>
        <p className="max-w-2xl text-sm text-gray-600">
          Enter a synthetic demo CNIC to retrieve exactly one identity record. There is no
          endpoint to browse or export the identity database.
        </p>
      </div>

      <IdentityLookupCard />

      <div className="rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-xs text-brand-800">
        Demo CNICs (synthetic only): 99900-0000001-1 (match case) · 99900-0000002-3 (mismatch
        case) · 99900-0000003-5 (manual review case). Run{' '}
        <code className="rounded bg-white/70 px-1 py-0.5">python -m app.database.seed</code> in
        the backend first.
      </div>
    </section>
  )
}
