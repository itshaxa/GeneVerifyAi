/**
 * Step 10: standardized loading / empty / error states.
 *
 * Every data view in the app renders through these three blocks so a user
 * always sees the same affordance, and so no component is tempted to render a
 * raw backend error body. Messages here are always human-written by the
 * caller: the only server text that reaches the screen is the safe
 * `ApiError.message` produced by `services/apiClient.ts`.
 */

import type { ReactNode } from 'react'

import { AlertIcon, ArrowRightIcon, InboxIcon, InfoIcon, RefreshIcon } from './Icons'

/** Shimmering placeholder bar used while data is in flight. */
export function Skeleton({ className = 'h-4 w-full' }: { className?: string }) {
  return <span className={`gv-skeleton block ${className}`} aria-hidden="true" />
}

interface LoadingBlockProps {
  label?: string
  /** 'row' keeps the spinner inline (table toolbars); default is a centred card body. */
  variant?: 'panel' | 'row' | 'inline'
  className?: string
}

/** Spinner plus meaningful text, announced politely to assistive tech. */
export function LoadingBlock({ label = 'Loading…', variant = 'panel', className = '' }: LoadingBlockProps) {
  if (variant === 'inline' || variant === 'row') {
    return (
      <p
        role="status"
        className={`flex items-center gap-2 text-sm text-gray-500 ${variant === 'row' ? 'py-2' : ''} ${className}`}
      >
        <Spinner />
        {label}
      </p>
    )
  }
  return (
    <div
      role="status"
      aria-busy="true"
      className={`flex flex-col items-center justify-center gap-3 px-4 py-10 text-center ${className}`}
    >
      <Spinner className="h-6 w-6" />
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  )
}

function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <span
      className={`inline-block shrink-0 animate-spin rounded-full border-2 border-gray-300 border-t-brand-600 ${className}`}
      aria-hidden="true"
    />
  )
}

interface EmptyStateProps {
  title: string
  description?: string
  icon?: ReactNode
  actionLabel?: string
  onAction?: () => void
  /** Optional href for the action - rendered as a link instead of a button. */
  actionHref?: string
  className?: string
}

/** Empty state with an explanation and the single next action it suggests. */
export function EmptyState({
  title,
  description,
  icon,
  actionLabel,
  onAction,
  actionHref,
  className = '',
}: EmptyStateProps) {
  return (
    <div
      className={`flex animate-gv-fade-in flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-gray-300 bg-gray-50/60 px-5 py-10 text-center ${className}`}
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-gray-400 ring-1 ring-gray-200">
        {icon ?? <InboxIcon size={18} />}
      </span>
      <p className="text-sm font-semibold text-gray-900">{title}</p>
      {description && <p className="max-w-md text-sm leading-relaxed text-gray-500">{description}</p>}
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700"
        >
          {actionLabel}
          <ArrowRightIcon size={15} />
        </button>
      )}
      {actionLabel && actionHref && (
        <a
          href={actionHref}
          className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700"
        >
          {actionLabel}
          <ArrowRightIcon size={15} />
        </a>
      )}
    </div>
  )
}

interface ErrorStateProps {
  /** Human-readable message. Never pass a raw payload or stack trace. */
  message: string
  /**
   * Heading of the panel. The default suits unexpected failures; routine
   * outcomes (a CNIC with no record behind it, an incomplete form) should pass
   * something neutral or use `InfoNotice` instead - Step 10 QA flagged
   * "Something went wrong" as misleading for those.
   */
  title?: string
  onRetry?: () => void
  retryLabel?: string
  className?: string
}

/** Error block: explains what failed and offers a retry when one makes sense. */
export function ErrorState({
  message,
  title = 'Something went wrong',
  onRetry,
  retryLabel = 'Try again',
  className = '',
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={`flex animate-gv-fade-in flex-col gap-2 rounded-xl bg-red-50 px-4 py-3.5 ring-1 ring-red-200 sm:flex-row sm:items-start ${className}`}
    >
      <span className="mt-0.5 shrink-0 text-red-600">
        <AlertIcon size={17} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-red-800">{title}</p>
        <p className="mt-0.5 text-sm leading-relaxed break-words text-red-700">{message}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 inline-flex shrink-0 items-center gap-1.5 self-start rounded-lg border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-700 transition hover:bg-red-100 sm:mt-0"
        >
          <RefreshIcon size={14} />
          {retryLabel}
        </button>
      )}
    </div>
  )
}

/**
 * Neutral notice for expected outcomes that are not failures: a CNIC that has
 * no record behind it, a form field that still needs completing. Kept apart
 * from `ErrorState` so a normal result is never dressed up as a crash.
 */
export function InfoNotice({
  message,
  title,
  className = '',
}: {
  message: string
  title?: string
  className?: string
}) {
  return (
    <div
      role="status"
      className={`flex items-start gap-2.5 rounded-xl bg-blue-50 px-4 py-3.5 ring-1 ring-blue-200 ${className}`}
    >
      <span className="mt-0.5 shrink-0 text-blue-600">
        <InfoIcon size={17} />
      </span>
      <div className="min-w-0 flex-1">
        {title && <p className="text-sm font-semibold text-blue-900">{title}</p>}
        <p className="text-sm leading-relaxed break-words text-blue-800">{message}</p>
      </div>
    </div>
  )
}

/**
 * Small-screen affordance for the horizontally scrollable tables. The wrappers
 * already scroll (the page never overflows), but without a hint the right-most
 * columns - status, decision and the row actions - simply look absent on a
 * phone, which Step 10 QA reported at 375/414/640.
 */
export function ScrollHint({ className = '' }: { className?: string }) {
  return (
    <p className={`mt-2 text-xs text-gray-500 lg:hidden ${className}`}>
      <ArrowRightIcon size={12} className="inline-block align-[-2px]" aria-hidden="true" />{' '}
      Scroll the table sideways to see every column.
    </p>
  )
}

interface SectionCardProps {
  title: string
  eyebrow?: string
  description?: string
  icon?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
  /** Heading level so the page keeps a semantic outline (h2 inside cards). */
  headingLevel?: 'h2' | 'h3'
}

/** Card with a numbered/eyebrow header - the shared frame for every section. */
export function SectionCard({
  title,
  eyebrow,
  description,
  icon,
  actions,
  children,
  className = '',
  bodyClassName = 'p-5 sm:p-6',
  headingLevel = 'h2',
}: SectionCardProps) {
  const Heading = headingLevel
  return (
    <section className={`gv-card overflow-hidden ${className}`}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 bg-gray-50/60 px-5 py-4">
        <div className="flex min-w-0 items-start gap-3">
          {icon && (
            <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700 ring-1 ring-brand-100">
              {icon}
            </span>
          )}
          <div className="min-w-0">
            {eyebrow && <p className="gv-eyebrow">{eyebrow}</p>}
            <Heading className="gv-section-title mt-0.5">{title}</Heading>
            {description && <p className="mt-1 text-sm text-gray-500">{description}</p>}
          </div>
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </header>
      <div className={bodyClassName}>{children}</div>
    </section>
  )
}

/** Small definition-list field reused by the case header, verify and report views. */
export function Field({
  label,
  children,
  className = '',
}: {
  label: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={`min-w-0 ${className}`}>
      <dt className="gv-eyebrow">{label}</dt>
      <dd className="mt-1 text-sm font-medium break-words text-gray-900">{children}</dd>
    </div>
  )
}
