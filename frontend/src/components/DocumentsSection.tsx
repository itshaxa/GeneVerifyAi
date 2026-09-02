import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import DnaComparisonResultView from './DnaComparisonResultView'
import DNAHelixAnimation from './DNAHelixAnimation'
import { SparklesIcon, UploadIcon } from './Icons'
import { ScrollHint } from './StateBlocks'
import { STR_PANEL_MARKERS } from './DnaAnalysisSection'
import { ApiError } from '../services/apiClient'
import { compareDna } from '../services/dnaService'
import {
  deleteDocument,
  downloadDocument,
  getDocumentExtraction,
  listDocuments,
  processDocument,
  uploadDocument,
} from '../services/documentService'
import { formatTimestamp } from '../utils/format'
import type {
  ConsistencyStatus,
  DnaComparisonResponse,
  DocumentExtractionResponse,
  VerificationDocument,
} from '../types/api'

/** Client-side mirror of the backend defaults (the server stays authoritative). */
const ALLOWED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg'] as const
const MAX_SIZE_BYTES = 10 * 1024 * 1024
const PANEL_SIZE = STR_PANEL_MARKERS.length

type UploadPhase = 'idle' | 'selected' | 'uploading' | 'success' | 'error'

const STATUS_STYLES: Record<VerificationDocument['processing_status'], string> = {
  UPLOADED: 'bg-blue-50 text-blue-700 ring-blue-200',
  PROCESSING: 'bg-amber-50 text-amber-700 ring-amber-200',
  PROCESSED: 'bg-green-50 text-green-700 ring-green-200',
  FAILED: 'bg-red-50 text-red-700 ring-red-200',
}

const DOCUMENT_TYPE_LABELS: Record<VerificationDocument['document_type'], string> = {
  DNA_REPORT: 'DNA Report',
  BLOOD_TEST: 'Blood Test',
  OTHER: 'Other',
}

const CONSISTENCY_STYLES: Record<ConsistencyStatus, string> = {
  CONSISTENT: 'bg-green-50 text-green-700 ring-green-200',
  INCONSISTENT: 'bg-red-50 text-red-700 ring-red-200',
  NOT_DETECTED: 'bg-gray-100 text-gray-600 ring-gray-300',
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatAllele(allele: number): string {
  return Number.isInteger(allele) ? String(allele) : allele.toFixed(1)
}

function validateFileLocally(file: File): string | null {
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!ALLOWED_EXTENSIONS.includes(extension as (typeof ALLOWED_EXTENSIONS)[number])) {
    return 'Unsupported file type. Allowed: PDF, PNG, JPG, JPEG.'
  }
  if (file.size > MAX_SIZE_BYTES) {
    return 'File exceeds the 10 MB limit.'
  }
  return null
}

/**
 * DNA document section: secure upload (Step 6) plus AI document intelligence
 * (Step 7). The AI only EXTRACTS a structured STR profile; the deterministic
 * STR engine performs every comparison. AI processing happens exclusively
 * on an explicit operator click — never on page load.
 */
export default function DocumentsSection({
  verificationId,
  onCompared,
}: {
  verificationId: string
  onCompared?: () => void
}) {
  const [documents, setDocuments] = useState<VerificationDocument[]>([])
  const [isListLoading, setIsListLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [phase, setPhase] = useState<UploadPhase>('idle')
  const [message, setMessage] = useState<string | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // Step 7: extraction results are fetched once and cached — no repeated AI calls.
  const [extractions, setExtractions] = useState<Record<string, DocumentExtractionResponse>>({})
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(null)
  const [analyzingId, setAnalyzingId] = useState<string | null>(null)
  const [aiError, setAiError] = useState<string | null>(null)
  const [compareResult, setCompareResult] = useState<DnaComparisonResponse | null>(null)
  const [isComparing, setIsComparing] = useState(false)
  const [compareError, setCompareError] = useState<string | null>(null)

  const loadDocuments = useCallback(async () => {
    setIsListLoading(true)
    setListError(null)
    try {
      const items = (await listDocuments(verificationId)).items
      setDocuments(items)
      // Stored extractions cost no AI calls — refresh them alongside the list.
      const processed = items.filter((document) => document.processing_status === 'PROCESSED')
      const fetched = await Promise.all(
        processed.map((document) => getDocumentExtraction(verificationId, document.document_id)),
      )
      setExtractions(Object.fromEntries(fetched.map((item) => [item.document_id, item])))
    } catch (err) {
      setListError(err instanceof ApiError ? err.message : 'Failed to load documents.')
    } finally {
      setIsListLoading(false)
    }
  }, [verificationId])

  useEffect(() => {
    void loadDocuments()
  }, [loadDocuments])

  const selectFile = (file: File | null) => {
    setMessage(null)
    if (!file) {
      setSelectedFile(null)
      setPhase('idle')
      return
    }
    const problem = validateFileLocally(file)
    if (problem) {
      setSelectedFile(null)
      setPhase('error')
      setMessage(problem)
      return
    }
    setSelectedFile(file)
    setPhase('selected')
  }

  const handleUpload = async () => {
    if (!selectedFile) return
    setPhase('uploading')
    setMessage(null)
    try {
      const uploaded = await uploadDocument(verificationId, selectedFile)
      setPhase('success')
      setMessage(`Document uploaded successfully — ${uploaded.document_id}`)
      setSelectedFile(null)
      if (inputRef.current) inputRef.current.value = ''
      await loadDocuments()
    } catch (err) {
      setPhase('error')
      setMessage(err instanceof ApiError ? err.message : 'Upload failed. Please try again.')
    }
  }

  const handleView = async (document: VerificationDocument) => {
    try {
      const blob = await downloadDocument(verificationId, document.document_id)
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank', 'noopener')
      // Give the new tab time to load the blob before releasing it.
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (err) {
      setListError(err instanceof ApiError ? err.message : 'Failed to open the document.')
    }
  }

  const handleDelete = async (document: VerificationDocument) => {
    if (!window.confirm(`Delete document ${document.document_id}?`)) return
    try {
      await deleteDocument(verificationId, document.document_id)
      setExtractions((previous) => {
        const next = { ...previous }
        delete next[document.document_id]
        return next
      })
      if (activeDocumentId === document.document_id) {
        setActiveDocumentId(null)
        setCompareResult(null)
      }
      await loadDocuments()
    } catch (err) {
      setListError(err instanceof ApiError ? err.message : 'Failed to delete the document.')
    }
  }

  const handleAnalyze = async (document: VerificationDocument) => {
    setAiError(null)
    setAnalyzingId(document.document_id)
    setCompareResult(null)
    setCompareError(null)
    try {
      await processDocument(verificationId, document.document_id)
      const extraction = await getDocumentExtraction(verificationId, document.document_id)
      setExtractions((previous) => ({ ...previous, [document.document_id]: extraction }))
      setActiveDocumentId(document.document_id)
      await loadDocuments()
    } catch (err) {
      setAiError(err instanceof ApiError ? err.message : 'AI analysis failed. Please try again.')
      await loadDocuments()
    } finally {
      setAnalyzingId(null)
    }
  }

  const handleCompareExtracted = async (extraction: DocumentExtractionResponse) => {
    if (!extraction.str_profile) return
    setCompareError(null)
    setIsComparing(true)
    try {
      setCompareResult(await compareDna(verificationId, extraction.str_profile))
      onCompared?.()
    } catch (err) {
      setCompareResult(null)
      setCompareError(err instanceof ApiError ? err.message : 'DNA comparison failed.')
    } finally {
      setIsComparing(false)
    }
  }

  const activeExtraction = activeDocumentId ? extractions[activeDocumentId] ?? null : null

  return (
    <section className="gv-card animate-gv-fade-up overflow-hidden">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 bg-gray-50/60 px-5 py-4">
        <div className="flex items-start gap-3">
          <span
            className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700 ring-1 ring-brand-100"
            aria-hidden="true"
          >
            <UploadIcon size={16} />
          </span>
          <div>
            <p className="gv-eyebrow">Stage 03 · Document</p>
            <h2 className="gv-section-title mt-0.5">Blood / DNA test document</h2>
          </div>
        </div>
      </header>
      <div className="p-5 sm:p-6">
      <p className="text-sm text-gray-500">
        Upload the DNA / blood-test report. Files are stored securely and are
        linked to this verification case only. AI extraction reads the document;
        DNA comparison is performed by the deterministic STR engine.
      </p>

      {/* Drag-and-drop upload area */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click()
        }}
        onDragOver={(event) => {
          event.preventDefault()
          setIsDragOver(true)
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={(event) => {
          event.preventDefault()
          setIsDragOver(false)
          selectFile(event.dataTransfer.files[0] ?? null)
        }}
        className={`mt-3 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-8 text-center transition ${
          isDragOver ? 'border-brand-500 bg-brand-50' : 'border-gray-300 bg-white hover:border-brand-400'
        }`}
      >
        <p className="text-sm font-medium text-gray-700">
          Drag &amp; drop your report here, or click to choose a file
        </p>
        <p className="mt-1 text-xs text-gray-400">PDF, JPG, JPEG, PNG · Maximum 10 MB</p>
        <input
          ref={inputRef}
          type="file"
          accept={ALLOWED_EXTENSIONS.join(',')}
          className="hidden"
          onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
        />
      </div>

      {/* Selection + upload controls */}
      {(selectedFile || phase !== 'idle') && (
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
          {selectedFile && (
            <span className="text-gray-700">
              Selected: <span className="font-medium">{selectedFile.name}</span>{' '}
              <span className="text-gray-400">({formatFileSize(selectedFile.size)})</span>
            </span>
          )}
          {phase === 'uploading' ? (
            <span className="inline-flex items-center gap-2 text-gray-500">
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" aria-hidden="true" />
              Uploading document…
            </span>
          ) : (
            <>
              <button
                type="button"
                onClick={() => void handleUpload()}
                disabled={!selectedFile}
                className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Upload Document
              </button>
              {(selectedFile || phase === 'success' || phase === 'error') && (
                <button
                  type="button"
                  onClick={() => {
                    selectFile(null)
                    if (inputRef.current) inputRef.current.value = ''
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
                >
                  {selectedFile ? 'Choose another file' : 'Reset'}
                </button>
              )}
            </>
          )}
        </div>
      )}

      {message && (
        <p
          className={`mt-3 rounded-lg border px-3 py-2 text-sm ${
            phase === 'success'
              ? 'border-green-200 bg-green-50 text-green-700'
              : 'border-red-200 bg-red-50 text-red-700'
          }`}
          role={phase === 'success' ? 'status' : 'alert'}
        >
          {message}
        </p>
      )}

      {/* Uploaded documents */}
      <h3 className="mt-6 text-xs font-semibold uppercase tracking-wide text-gray-400">
        Uploaded documents
      </h3>
      {listError && (
        <p className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {listError}
        </p>
      )}
      {aiError && (
        <p className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {aiError}
        </p>
      )}
      {isListLoading ? (
        <p className="mt-2 text-sm text-gray-500">Loading documents…</p>
      ) : documents.length === 0 ? (
        <p className="mt-2 text-sm text-gray-500">No documents uploaded for this case yet.</p>
      ) : (
        <>
        <div className="mt-2 overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-3 py-2">Document</th>
                <th className="px-3 py-2">File</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Uploaded</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {documents.map((document) => {
                const extraction = extractions[document.document_id]
                const isAnalyzing = analyzingId === document.document_id
                return (
                  <tr key={document.document_id}>
                    <td className="px-3 py-1.5 font-mono text-xs text-gray-800">{document.document_id}</td>
                    <td className="px-3 py-1.5 text-gray-700">
                      {document.original_filename}
                      <span className="ml-1 text-xs text-gray-400">({formatFileSize(document.file_size)})</span>
                    </td>
                    <td className="px-3 py-1.5 text-gray-600">{DOCUMENT_TYPE_LABELS[document.document_type]}</td>
                    <td className="px-3 py-1.5">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${STATUS_STYLES[document.processing_status]}`}>
                        {document.processing_status}
                      </span>
                      {document.processing_status === 'PROCESSED' && extraction && (
                        <p className="mt-0.5 text-[11px] text-green-700">
                          DNA profile extracted · {extraction.extracted_marker_count} / {PANEL_SIZE} markers
                        </p>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-gray-600">{formatTimestamp(document.created_at)}</td>
                    <td className="px-3 py-1.5 text-right">
                      {(document.processing_status === 'UPLOADED' || document.processing_status === 'FAILED') && (
                        <button
                          type="button"
                          onClick={() => void handleAnalyze(document)}
                          disabled={analyzingId !== null}
                          className="mr-2 inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-2.5 py-1 text-xs font-semibold text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {isAnalyzing && (
                            <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" aria-hidden="true" />
                          )}
                          {document.processing_status === 'FAILED' ? 'Retry AI analysis' : 'Analyze with AI'}
                        </button>
                      )}
                      {document.processing_status === 'PROCESSED' && (
                        <button
                          type="button"
                          onClick={() => {
                            setActiveDocumentId(
                              activeDocumentId === document.document_id ? null : document.document_id,
                            )
                            setCompareResult(null)
                            setCompareError(null)
                          }}
                          className="mr-2 font-medium text-brand-700 hover:underline"
                        >
                          {activeDocumentId === document.document_id ? 'Hide extraction' : 'View extraction'}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => void handleView(document)}
                        className="mr-2 font-medium text-brand-700 hover:underline"
                      >
                        View
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleDelete(document)}
                        className="font-medium text-red-600 hover:underline"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <ScrollHint />
        </>
      )}

      {analyzingId && (
        <p className="mt-3 inline-flex items-center gap-2 text-sm text-gray-600" role="status">
          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" aria-hidden="true" />
          AI is analyzing the document…
        </p>
      )}

      {/* Decorative helix for the existing AI extraction state; the text above stays authoritative. */}
      <DNAHelixAnimation active={Boolean(analyzingId)} className="mt-1 h-44 w-full sm:h-56" />

      {/* AI extraction panel */}
      {activeExtraction && activeDocumentId && (
        <ExtractionPanel
          extraction={activeExtraction}
          isComparing={isComparing}
          compareResult={compareResult}
          compareError={compareError}
          onCompare={() => void handleCompareExtracted(activeExtraction)}
        />
      )}

      <p className="mt-4 text-xs text-gray-500">
        AI extracts information from the submitted document. DNA comparison is
        performed by a deterministic STR engine. AI-extracted data always
        requires deterministic validation and is never an identity verdict.
      </p>
      </div>
    </section>
  )
}

function ConsistencyBadge({ label, value }: { label: string; value: ConsistencyStatus | null }) {
  if (!value) return null
  return (
    <span className={`ml-2 inline-flex items-center rounded-full px-2 py-0.5 align-middle text-[10px] font-medium ring-1 ${CONSISTENCY_STYLES[value]}`}>
      {label}: {value.replaceAll('_', ' ')}
    </span>
  )
}

function ExtractionPanel({
  extraction,
  isComparing,
  compareResult,
  compareError,
  onCompare,
}: {
  extraction: DocumentExtractionResponse
  isComparing: boolean
  compareResult: DnaComparisonResponse | null
  compareError: string | null
  onCompare: () => void
}) {
  const profile = extraction.str_profile ?? {}
  const orderedMarkers = STR_PANEL_MARKERS.filter((marker) => marker in profile)
  const failed = extraction.extraction_status === 'FAILED'

  return (
    <section className="mt-5 rounded-xl border border-brand-200 bg-brand-50/30 px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="gv-eyebrow">Stage 04 · AI Extraction</p>
          <h3 className="gv-section-title mt-0.5">Extracted document data</h3>
        </div>
        <span className="gv-badge bg-amber-50 text-amber-800 ring-amber-200">
          <SparklesIcon size={13} />
          AI output — needs deterministic validation
        </span>
      </div>

      {failed ? (
        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          Extraction failed{extraction.validation_note ? `: ${extraction.validation_note}` : '.'}
        </p>
      ) : (
        <>
          <dl className="mt-3 grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
            <ExtractionField label="Patient Name" value={extraction.patient_name}>
              <ConsistencyBadge label="Name" value={extraction.name_consistency} />
            </ExtractionField>
            <ExtractionField label="CNIC" value={extraction.cnic}>
              <ConsistencyBadge label="CNIC" value={extraction.cnic_consistency} />
            </ExtractionField>
            <ExtractionField label="Report Date" value={extraction.report_date} />
            <ExtractionField label="Laboratory Ref." value={extraction.laboratory_reference} />
          </dl>

          <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
            AI-extracted STR profile · {extraction.extracted_marker_count} / {PANEL_SIZE} markers
          </p>
          {orderedMarkers.length === 0 ? (
            <p className="mt-2 text-sm text-gray-500">
              No STR markers could be extracted from this document.
            </p>
          ) : (
            <div className="mt-2 overflow-x-auto rounded-lg border border-gray-200">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                  <tr>
                    <th className="px-3 py-2">Marker</th>
                    <th className="px-3 py-2">Allele 1</th>
                    <th className="px-3 py-2">Allele 2</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {orderedMarkers.map((marker) => (
                    <tr key={marker}>
                      <td className="px-3 py-1.5 font-mono text-xs text-gray-800">{marker}</td>
                      <td className="px-3 py-1.5 font-mono text-xs text-gray-600">{formatAllele(profile[marker][0])}</td>
                      <td className="px-3 py-1.5 font-mono text-xs text-gray-600">{formatAllele(profile[marker][1])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="mt-2 text-xs text-gray-500">
            Comparison is performed by the deterministic STR engine — the AI
            never decides whether a profile matches.
          </p>

          {orderedMarkers.length > 0 && (
            <button
              type="button"
              onClick={onCompare}
              disabled={isComparing}
              className="mt-3 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isComparing ? 'Comparing…' : 'Compare With Registered DNA'}
            </button>
          )}

          <DNAHelixAnimation active={isComparing} className="mt-2 h-36 w-full sm:h-44" />

          {compareError && (
            <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
              {compareError}
            </p>
          )}

          {compareResult && (
            <div className="mt-4">
              <DnaComparisonResultView result={compareResult} />
            </div>
          )}
        </>
      )}
    </section>
  )
}

function ExtractionField({
  label,
  value,
  children,
}: {
  label: string
  value: string | null
  children?: ReactNode
}) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className="mt-0.5 text-gray-800">
        {value ?? '—'}
        {children}
      </dd>
    </div>
  )
}
