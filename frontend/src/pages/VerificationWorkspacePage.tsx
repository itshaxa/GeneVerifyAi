import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'

import CaseStatusBadge from '../components/CaseStatusBadge'
import {
  ArrowRightIcon,
  CheckCircleIcon,
  InfoIcon,
  SearchIcon,
  ShieldIcon,
  UploadIcon,
  UserIcon,
} from '../components/Icons'
import { ErrorState, Field, InfoNotice } from '../components/StateBlocks'
import VerificationPipeline from '../components/VerificationPipeline'
import { createVerification } from '../services/verificationService'
import { lookupIdentityByCnic } from '../services/identityService'
import type { IdentityLookupResponse, VerificationCase } from '../types/api'
import { cnicDigitCount, formatCnic, formatTimestamp } from '../utils/format'
import { describeError, isNotFound } from '../utils/errorMessage'

/**
 * Verification workspace — the CNIC → identity → case half of the workflow.
 *
 * Step 10 keeps the exact flow of Step 4 and only improves it: a large CNIC
 * field that masks as #####-#######-# while typing, live formatting feedback,
 * an identity confirmation card and a next-step card after creation. No
 * validation rule is decided here - the backend still validates the CNIC and
 * owns the identity lookup, and the input is sent to it unchanged.
 */

/** Same canonical shape the backend accepts (`app/core/cnic.py`). */
const CANONICAL_CNIC = /^\d{5}-\d{7}-\d$/

const STEPS = ['Enter CNIC', 'Confirm identity', 'Case created'] as const

/** The ordinary "no such record" answer of the lookup endpoint. */
const NOT_FOUND_MESSAGE =
  'No synthetic identity record exists for this CNIC, so no case can be opened for it.'

export default function VerificationWorkspacePage() {
  const [cnic, setCnic] = useState('')
  const [identity, setIdentity] = useState<IdentityLookupResponse | null>(null)
  const [verificationCase, setVerificationCase] = useState<VerificationCase | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  // `error` is reserved for genuine failures; `notice` carries expected
  // outcomes (incomplete CNIC, no matching record) so they are not shown as a
  // crash - see the Step 10 QA pass.
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const digits = cnicDigitCount(cnic)
  const isWellFormed = CANONICAL_CNIC.test(cnic)
  const feedback = useMemo(() => {
    if (digits === 0) return { tone: 'neutral' as const, text: 'Format: 5 digits, 7 digits, 1 digit (13 in total).' }
    if (digits < 13) return { tone: 'neutral' as const, text: `${digits} of 13 digits entered.` }
    if (!isWellFormed) return { tone: 'neutral' as const, text: 'Dashes are added automatically — ready to search.' }
    return { tone: 'ready' as const, text: 'CNIC format looks complete.' }
  }, [digits, isWellFormed])

  const activeStep = verificationCase ? 2 : identity ? 1 : 0

  /** Editing the CNIC invalidates anything already resolved from it. */
  function handleCnicChange(value: string) {
    setCnic(formatCnic(value))
    if (identity || verificationCase) {
      setIdentity(null)
      setVerificationCase(null)
    }
    setError(null)
    setNotice(null)
  }

  const reset = () => {
    setIdentity(null)
    setVerificationCase(null)
    setError(null)
    setNotice(null)
  }

  const handleFindIdentity = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    reset()
    if (!cnic.trim()) {
      setNotice('Enter a CNIC to continue.')
      return
    }
    if (digits !== 13) {
      // Checked before asking so an obviously incomplete entry never costs a
      // request. The backend still validates whatever is finally submitted.
      setNotice('Enter all 13 digits of a CNIC (5 digits, 7 digits, 1 digit).')
      return
    }
    setIsSearching(true)
    try {
      setIdentity(await lookupIdentityByCnic(cnic))
    } catch (err) {
      if (isNotFound(err)) {
        setNotice(NOT_FOUND_MESSAGE)
      } else {
        setError(describeError(err, 'The identity lookup could not be completed.'))
      }
    } finally {
      setIsSearching(false)
    }
  }

  const handleCreateCase = async () => {
    if (!identity) return
    // Clear only the created-case/error state; keep the confirmed identity.
    setVerificationCase(null)
    setError(null)
    setIsCreating(true)
    try {
      setVerificationCase(await createVerification(identity.cnic))
    } catch (err) {
      setError(describeError(err, 'The verification case could not be created.'))
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl">
      <header className="mb-6 sm:mb-8">
        <p className="gv-eyebrow">Verify Identity</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
          Start a verification
        </h1>
        <p className="mt-1.5 text-sm leading-relaxed text-gray-600">
          Look up a synthetic identity record by CNIC, confirm who it belongs to, then open a
          verification case for their blood / DNA test document.
        </p>
      </header>

      {/* Mini stepper - presentation of the flow, not a state machine copy. */}
      <ol className="mb-6 flex flex-wrap items-center gap-x-2 gap-y-2 text-xs" aria-label="Verification steps">
        {STEPS.map((step, index) => {
          const isDone = index < activeStep
          const isCurrent = index === activeStep
          return (
            <li key={step} className="flex items-center gap-2">
              <span
                aria-current={isCurrent ? 'step' : undefined}
                className={`gv-badge ${
                  isDone
                    ? 'bg-brand-50 text-brand-700 ring-brand-200'
                    : isCurrent
                      ? 'bg-white text-gray-900 ring-gray-300'
                      : 'bg-gray-100 text-gray-500 ring-gray-200'
                }`}
              >
                <span className="font-mono text-[11px] font-medium">{`0${index + 1}`}</span>
                {isDone ? <CheckCircleIcon size={13} /> : null}
                {step}
              </span>
              {index < STEPS.length - 1 && (
                <span className="text-gray-300" aria-hidden="true">
                  <ArrowRightIcon size={13} />
                </span>
              )}
            </li>
          )
        })}
      </ol>

      {/* Step 1: CNIC entry */}
      <section className="gv-card animate-gv-fade-up p-5 sm:p-6" aria-labelledby="cnic-heading">
        <h2 id="cnic-heading" className="gv-section-title">
          <span className="text-brand-600" aria-hidden="true">
            <SearchIcon size={15} />
          </span>{' '}
          Enter CNIC
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          Only records that exist in the synthetic dataset can be resolved.
        </p>

        <form onSubmit={handleFindIdentity} className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-start">
          <div className="min-w-0 flex-1">
            <label htmlFor="cnic-field" className="gv-eyebrow">
              CNIC number
            </label>
            <input
              id="cnic-field"
              type="text"
              value={cnic}
              onChange={(event) => handleCnicChange(event.target.value)}
              placeholder="99900-0000001-1"
              inputMode="numeric"
              autoComplete="off"
              spellCheck={false}
              maxLength={15}
              aria-describedby="cnic-feedback"
              aria-invalid={digits > 0 && digits < 13 ? true : undefined}
              className="mt-1.5 w-full rounded-xl border border-gray-300 bg-white px-4 py-3.5 font-mono text-xl tracking-[0.08em] text-gray-900 shadow-sm transition focus:border-brand-500 focus:ring-2 focus:ring-brand-200 focus:outline-none sm:text-2xl"
            />
            <p
              id="cnic-feedback"
              aria-live="polite"
              className={`mt-2 flex items-center gap-1.5 text-xs ${
                feedback.tone === 'ready' ? 'text-brand-700' : 'text-gray-500'
              }`}
            >
              {feedback.tone === 'ready' ? <CheckCircleIcon size={13} /> : <InfoIcon size={13} />}
              {feedback.text}
            </p>
          </div>
          <button
            type="submit"
            disabled={isSearching || digits === 0}
            className="gv-btn gv-btn-primary gv-btn-lg mt-6 shrink-0 self-start sm:mt-[26px]"
          >
            {isSearching ? (
              <>
                <span
                  className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
                  aria-hidden="true"
                />
                Searching…
              </>
            ) : (
              <>
                <SearchIcon size={16} />
                Find Identity
              </>
            )}
          </button>
        </form>
      </section>

      {notice && (
        <div className="mt-4">
          <InfoNotice message={notice} />
        </div>
      )}

      {error && (
        <div className="mt-4">
          <ErrorState
            title="The request failed"
            message={error}
            onRetry={isCreating ? () => void handleCreateCase() : undefined}
          />
        </div>
      )}

      {/* Step 2: identity confirmation */}
      {identity && !verificationCase && (
        <section
          className="gv-card animate-gv-fade-up mt-6 p-5 sm:p-6"
          aria-labelledby="confirm-heading"
        >
          <div className="flex items-start gap-3">
            <span
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700 ring-1 ring-brand-100"
              aria-hidden="true"
            >
              <UserIcon size={18} />
            </span>
            <div className="min-w-0">
              <h2 id="confirm-heading" className="gv-section-title">
                Confirm the identity
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                Check these details against the request before opening a case.
              </p>
            </div>
            <span className="gv-badge ml-auto hidden bg-brand-50 text-brand-700 ring-brand-200 sm:inline-flex">
              <ShieldIcon size={13} />
              Record found
            </span>
          </div>

          <dl className="mt-5 grid grid-cols-1 gap-x-8 gap-y-4 border-t border-gray-100 pt-5 text-sm sm:grid-cols-2">
            <Field label="Name">{identity.name}</Field>
            <Field label="CNIC">
              <span className="font-mono">{identity.cnic}</span>
            </Field>
            <Field label="Father's name">{identity.father_name}</Field>
            <Field label="Date of birth">{identity.date_of_birth}</Field>
            <Field label="Gender">
              <span className="capitalize">{identity.gender}</span>
            </Field>
            <Field label="Record status">
              <span className="capitalize">{identity.status.replace(/_/g, ' ')}</span>
            </Field>
            <Field label="Address" className="sm:col-span-2">
              <span className="font-normal text-gray-700">{identity.address}</span>
            </Field>
          </dl>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void handleCreateCase()}
              disabled={isCreating}
              className="gv-btn gv-btn-primary gv-btn-lg"
            >
              {isCreating ? 'Creating case…' : 'Create Verification Case'}
              {!isCreating && <ArrowRightIcon size={16} />}
            </button>
            <button
              type="button"
              onClick={() => {
                reset()
                setCnic('')
              }}
              className="gv-btn gv-btn-ghost"
            >
              Search a different CNIC
            </button>
          </div>

          <p className="mt-5 border-t border-gray-100 pt-4 text-xs leading-relaxed text-gray-500">
            The DNA / STR reference profile is intentionally not shown here — it stays internal to the
            verification workflow and is only ever compared by the backend engine.
          </p>
        </section>
      )}

      {/* Step 3: case created + next step */}
      {verificationCase && (
        <section
          className="animate-gv-pop mt-6 overflow-hidden rounded-2xl border border-brand-200 bg-gradient-to-br from-brand-50/90 to-white shadow-sm"
          aria-labelledby="created-heading"
        >
          <div className="p-5 sm:p-6">
            <div className="flex items-start gap-3">
              <span
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white shadow-sm"
                aria-hidden="true"
              >
                <CheckCircleIcon size={19} />
              </span>
              <div className="min-w-0">
                <h2 id="created-heading" className="gv-section-title">
                  Verification case created
                </h2>
                <p className="mt-1 text-sm text-gray-600">
                  The case is open and ready for its supporting document.
                </p>
              </div>
              <div className="ml-auto hidden sm:block">
                <CaseStatusBadge status={verificationCase.status} size="lg" />
              </div>
            </div>

            <dl className="mt-5 grid grid-cols-1 gap-x-8 gap-y-4 rounded-xl border border-brand-100 bg-white/80 p-4 text-sm sm:grid-cols-2">
              <Field label="Verification ID">
                <span className="font-mono text-base font-bold text-brand-800">
                  {verificationCase.verification_id}
                </span>
              </Field>
              <Field label="Linked identity">
                {verificationCase.identity.name}{' '}
                <span className="font-mono text-xs text-gray-500">{verificationCase.identity.cnic}</span>
              </Field>
              <Field label="Created by">{verificationCase.created_by_username}</Field>
              <Field label="Created">{formatTimestamp(verificationCase.created_at)}</Field>
            </dl>

            <div className="mt-5 flex flex-col gap-3 rounded-xl border border-dashed border-brand-300 bg-white p-4 sm:flex-row sm:items-center">
              <span
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-brand-700 ring-1 ring-brand-200"
                aria-hidden="true"
              >
                <UploadIcon size={18} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-gray-900">Next: upload the blood / DNA test document</p>
                <p className="mt-0.5 text-xs leading-relaxed text-gray-500">
                  On the case page you can attach the document, run the AI extraction, compare the STR
                  profile and generate the report.
                </p>
              </div>
              <Link
                to={`/verifications/${verificationCase.verification_id}`}
                className="gv-btn gv-btn-primary shrink-0"
              >
                Open case
                <ArrowRightIcon size={15} />
              </Link>
            </div>

            <div className="mt-5 flex flex-wrap gap-3">
              <Link to="/verifications" className="gv-btn gv-btn-secondary">
                All my cases
              </Link>
              <button
                type="button"
                onClick={() => {
                  reset()
                  setCnic('')
                  window.scrollTo({ top: 0, behavior: 'instant' })
                }}
                className="gv-btn gv-btn-ghost"
              >
                Verify another identity
              </button>
            </div>
          </div>
        </section>
      )}

      {/* The rest of the workflow, for orientation only. */}
      <section className="gv-card animate-gv-fade-up mt-6 p-5 sm:p-6" aria-labelledby="pipeline-preview-heading">
        <h2 id="pipeline-preview-heading" className="gv-section-title">
          What happens after the case is created
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          Every later stage is recorded in the case's audit trail and reflected in its report.
        </p>
        <div className="mt-4">
          <VerificationPipeline variant="reference" />
        </div>
      </section>
    </div>
  )
}
