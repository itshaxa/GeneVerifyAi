/**
 * Document endpoints of a verification case (Step 6).
 *
 * Uploads are multipart/form-data and downloads are binary — both go through
 * the shared apiClient so auth handling and error envelopes stay consistent.
 */

import { apiFetch, apiFetchRaw } from './apiClient'
import type {
  DocumentExtractionResponse,
  DocumentType,
  ProcessDocumentResponse,
  VerificationDocument,
  VerificationDocumentListResponse,
} from '../types/api'

function documentsPath(verificationId: string): string {
  return `/verifications/${encodeURIComponent(verificationId)}/documents`
}

export function listDocuments(verificationId: string): Promise<VerificationDocumentListResponse> {
  return apiFetch<VerificationDocumentListResponse>(documentsPath(verificationId))
}

export function uploadDocument(
  verificationId: string,
  file: File,
  documentType: DocumentType = 'DNA_REPORT',
): Promise<VerificationDocument> {
  const form = new FormData()
  form.append('file', file)
  form.append('document_type', documentType)
  return apiFetch<VerificationDocument>(documentsPath(verificationId), {
    method: 'POST',
    body: form,
  })
}

/** Fetch the stored file bytes; the browser never sees storage paths. */
export async function downloadDocument(verificationId: string, documentId: string): Promise<Blob> {
  const response = await apiFetchRaw(
    `${documentsPath(verificationId)}/${encodeURIComponent(documentId)}/file`,
  )
  return response.blob()
}

export function deleteDocument(verificationId: string, documentId: string): Promise<void> {
  return apiFetch<void>(
    `${documentsPath(verificationId)}/${encodeURIComponent(documentId)}`,
    { method: 'DELETE' },
  )
}

// --- Step 7: AI document intelligence ------------------------------------

/** Start the AI extraction pipeline for one uploaded document. */
export function processDocument(
  verificationId: string,
  documentId: string,
): Promise<ProcessDocumentResponse> {
  return apiFetch<ProcessDocumentResponse>(
    `${documentsPath(verificationId)}/${encodeURIComponent(documentId)}/process`,
    { method: 'POST' },
  )
}

/** Fetch the stored extraction result — never triggers another AI call. */
export function getDocumentExtraction(
  verificationId: string,
  documentId: string,
): Promise<DocumentExtractionResponse> {
  return apiFetch<DocumentExtractionResponse>(
    `${documentsPath(verificationId)}/${encodeURIComponent(documentId)}/extraction`,
  )
}
