/**
 * Step 10: the GeneVerify verification pipeline as a visual component.
 *
 * UI representation only - no backend logic is duplicated or re-derived here.
 * When a case report is supplied, each stage's state comes straight from the
 * fields the Step 9 report API already returns (`document.available`,
 * `ai_extraction.available`, `dna_analysis.available`, `evidence.available`,
 * `decision.available`) plus the recorded audit trail. Nothing is inferred
 * from timers, heuristics or client-side scoring.
 */

import type { ReactNode } from 'react'

import type { VerificationReport } from '../types/api'
import {
  AlertIcon,
  CheckIcon,
  ClockIcon,
  CompareIcon,
  FileTextIcon,
  FolderIcon,
  GavelIcon,
  PlusIcon,
  ScaleIcon,
  SearchIcon,
  SparklesIcon,
  UploadIcon,
} from './Icons'

type StageState = 'done' | 'waiting' | 'attention' | 'reference'

interface Stage {
  code: string
  label: string
  caption: string
  Icon: typeof PlusIcon
}

/** The eight workflow stages, in order. */
export const PIPELINE_STAGES: Stage[] = [
  { code: '01', label: 'Identity', caption: 'CNIC lookup', Icon: SearchIcon },
  { code: '02', label: 'Case', caption: 'Verification created', Icon: FolderIcon },
  { code: '03', label: 'Document', caption: 'Blood / DNA upload', Icon: UploadIcon },
  { code: '04', label: 'AI Extraction', caption: 'STR profile read', Icon: SparklesIcon },
  { code: '05', label: 'STR Comparison', caption: '20-marker engine', Icon: CompareIcon },
  { code: '06', label: 'Evidence', caption: 'Score 70 / 20 / 10', Icon: ScaleIcon },
  { code: '07', label: 'Decision', caption: 'Deterministic outcome', Icon: GavelIcon },
  { code: '08', label: 'Report', caption: 'Auditable PDF', Icon: FileTextIcon },
]

/** Literal class names so the entrance stagger stays greppable. */
const STAGGER_CLASSES = [
  'gv-stagger-1',
  'gv-stagger-2',
  'gv-stagger-3',
  'gv-stagger-4',
  'gv-stagger-4',
  'gv-stagger-4',
  'gv-stagger-4',
  'gv-stagger-4',
]

interface Props {
  /** When present, stage states are derived from this backend report payload. */
  report?: VerificationReport | null
  /** True while the report is still being fetched (renders placeholder tiles). */
  loading?: boolean
  /**
   * True when the report could not be read. Stage states are then *unknown*,
   * which is stated plainly instead of being shown as "nothing recorded".
   */
  unavailable?: boolean
  /** 'reference' shows the workflow without claiming any progress. */
  variant?: 'reference' | 'case'
  className?: string
}

/**
 * Map the backend report sections onto the eight stage states.
 * Returns `null` when no report is available yet.
 */
function deriveStates(report: VerificationReport): StageState[] {
  const done = (available: boolean, failed = false): StageState =>
    failed ? 'attention' : available ? 'done' : 'waiting'

  const reportGenerated = report.audit_timeline.some((event) => event.event_type === 'REPORT_GENERATED')

  return [
    // 01 Identity + 02 Case: the report could only be produced for an existing
    // case that resolved to a real identity record.
    'done',
    'done',
    // 03 Document
    done(report.document.available, report.document.available && report.document.processing_status === 'FAILED'),
    // 04 AI extraction
    done(
      report.ai_extraction.available,
      report.ai_extraction.available && report.ai_extraction.extraction_status === 'FAILED',
    ),
    // 05 STR comparison
    done(
      report.dna_analysis.available,
      report.dna_analysis.available && report.dna_analysis.classification === 'INVALID',
    ),
    // 06 Evidence, 07 Decision
    done(report.evidence.available),
    done(report.decision.available),
    // 08 Report: complete only once a PDF has actually been generated.
    reportGenerated ? 'done' : 'waiting',
  ]
}

const STATE_META: Record<StageState, { word: string; className: string; ring: string }> = {
  done: { word: 'Recorded', className: 'text-brand-700', ring: 'bg-brand-600 text-white' },
  waiting: { word: 'Pending', className: 'text-gray-400', ring: 'bg-white text-gray-400 ring-1 ring-gray-200' },
  attention: { word: 'Needs review', className: 'text-amber-700', ring: 'bg-amber-500 text-white' },
  reference: { word: '', className: 'text-gray-500', ring: 'bg-white text-brand-700 ring-1 ring-brand-200' },
}

function StateGlyph({ state }: { state: StageState }) {
  if (state === 'done') return <CheckIcon size={13} />
  if (state === 'attention') return <AlertIcon size={13} />
  return <ClockIcon size={13} />
}

export default function VerificationPipeline({
  report = null,
  loading = false,
  unavailable = false,
  variant = 'reference',
  className = '',
}: Props) {
  // Nothing can be claimed about progress without a readable report.
  const showCaseStates = variant === 'case' && !unavailable
  const states: StageState[] =
    showCaseStates && report ? deriveStates(report) : PIPELINE_STAGES.map(() => 'reference')
  const hasStates = showCaseStates && Boolean(report)

  const completedCount = states.filter((state) => state === 'done').length
  const progressPercent = variant === 'case' ? Math.round((completedCount / states.length) * 100) : 0

  return (
    <div className={className}>
      {variant === 'case' && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-gray-600">
            {loading ? (
              'Checking recorded stages…'
            ) : unavailable ? (
              <>
                <span className="font-semibold text-gray-900">Stage status unavailable</span> - the
                case report could not be read, so no stage is claimed as recorded.
              </>
            ) : (
              <>
                <span className="font-semibold text-gray-900">
                  {completedCount} of {states.length}
                </span>{' '}
                stages recorded from backend data
              </>
            )}
          </p>
          <p className="gv-eyebrow">{hasStates ? `${progressPercent}%` : '—'}</p>
        </div>
      )}

      {variant === 'case' && hasStates && (
        <div
          className="mb-5 h-1.5 overflow-hidden rounded-full bg-gray-200/80"
          role="progressbar"
          aria-valuenow={progressPercent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Pipeline stages recorded"
        >
          <div
            className="h-full rounded-full bg-brand-500 transition-[width] duration-500 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      )}

      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
        {PIPELINE_STAGES.map((stage, index) => {
          const state = states[index] ?? 'reference'
          const meta = STATE_META[state]
          const { Icon } = stage
          const body: ReactNode = loading && variant === 'case' ? null : (
            <>
              <span
                className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors duration-300 ${meta.ring}`}
                aria-hidden="true"
              >
                <Icon size={15} />
              </span>
              <p className="mt-2 text-xs leading-tight font-semibold break-words text-gray-900">
                {stage.label}
              </p>
              <p className={`mt-0.5 text-[11px] leading-tight ${state === 'waiting' ? 'text-gray-400' : meta.className}`}>
                {variant === 'case' ? meta.word : stage.caption}
              </p>
            </>
          )

          return (
            <li
              key={stage.code}
              className={`gv-card gv-card-hover animate-gv-fade-up relative flex flex-col p-3 ${STAGGER_CLASSES[index] ?? ''}`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] font-medium tracking-wider text-gray-500">{stage.code}</span>
                {variant === 'case' && !loading && (
                  <span className={`${meta.className} flex items-center gap-1`} aria-hidden="true">
                    <StateGlyph state={state} />
                  </span>
                )}
              </div>
              {body ?? <span className="mt-2 block h-14 animate-pulse rounded-md bg-gray-100" aria-hidden="true" />}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
