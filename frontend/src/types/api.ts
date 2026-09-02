/**
 * Shared API contract types. These mirror the backend Pydantic schemas and
 * must stay in sync with them.
 */

/** Response contract of GET /api/v1/health */
export interface HealthStatus {
  status: string
  app: string
  environment: string
  version: string
}

/** Uniform error envelope returned by the backend on failures. */
export interface ApiErrorPayload {
  detail: string
  code: string | null
}

export type Gender = 'male' | 'female'

export type IdentityStatus = 'active' | 'inactive' | 'under_review'

/**
 * Safe CNIC lookup response (GET /api/v1/identity/{cnic}).
 * Deliberately does NOT include the DNA profile.
 */
export interface IdentityLookupResponse {
  cnic: string
  name: string
  father_name: string
  date_of_birth: string
  gender: Gender
  address: string
  photo_reference: string | null
  status: IdentityStatus
}

export type UserRole = 'admin' | 'officer'

/** Safe user view returned by the auth endpoints (never contains password_hash). */
export interface AuthUser {
  id: number
  username: string
  role: UserRole
  is_active: boolean
}

/** Response contract of POST /api/v1/auth/login */
export interface LoginResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

export type CaseStatus = 'draft' | 'in_progress' | 'completed' | 'review_required' | 'cancelled'

/** Safe identity reference embedded in verification case responses (no DNA). */
export interface CaseIdentitySummary {
  cnic: string
  name: string
  father_name: string
  date_of_birth: string
  gender: Gender
  status: IdentityStatus
}

/** Response contract of the /api/v1/verifications endpoints. */
export interface VerificationCase {
  verification_id: string
  status: CaseStatus
  identity: CaseIdentitySummary
  created_by_user_id: number
  created_by_username: string
  created_at: string
  updated_at: string
}

/** Response contract of GET /api/v1/verifications */
export interface VerificationCaseListResponse {
  items: VerificationCase[]
  total: number
}

export type MarkerStatus = 'MATCH' | 'MISMATCH' | 'MISSING_REFERENCE' | 'MISSING_SUBMITTED' | 'INVALID'

export type ComparisonClassification = 'EXACT_MATCH' | 'PARTIAL_MATCH' | 'NO_MATCH' | 'INVALID'

/** Per-marker outcome of the deterministic STR comparison. */
export interface MarkerComparison {
  marker: string
  status: MarkerStatus
  reference_alleles: number[] | null
  submitted_alleles: number[] | null
  reason: string | null
}

/** Aggregate counts of one comparison (never a forensic probability). */
export interface ComparisonSummary {
  total_markers: number
  matched: number
  mismatched: number
  missing: number
  invalid: number
  match_percentage: number
}

/** Response contract of POST /api/v1/verifications/{id}/dna/compare */
export interface DnaComparisonResponse {
  verification_id: string
  classification: ComparisonClassification
  summary: ComparisonSummary
  markers: MarkerComparison[]
  compared_at: string
}

export type DocumentType = 'DNA_REPORT' | 'BLOOD_TEST' | 'OTHER'

export type ProcessingStatus = 'UPLOADED' | 'PROCESSING' | 'PROCESSED' | 'FAILED'

/** Safe metadata view of one uploaded document (no storage paths, no DNA). */
export interface VerificationDocument {
  document_id: string
  original_filename: string
  document_type: DocumentType
  content_type: string
  file_size: number
  processing_status: ProcessingStatus
  uploaded_by: string
  created_at: string
  updated_at: string
}

/** Response contract of GET /api/v1/verifications/{id}/documents */
export interface VerificationDocumentListResponse {
  verification_id: string
  items: VerificationDocument[]
  total: number
}

// --- Step 7: AI document intelligence ------------------------------------

export type ExtractionStatus = 'SUCCEEDED' | 'FAILED'

export type ConsistencyStatus = 'CONSISTENT' | 'INCONSISTENT' | 'NOT_DETECTED'

/** Response contract of POST .../documents/{document_id}/process */
export interface ProcessDocumentResponse {
  document_id: string
  processing_status: ProcessingStatus
  extraction_status: ExtractionStatus | null
  extracted_marker_count: number | null
}

/**
 * Response contract of GET .../documents/{document_id}/extraction.
 * AI-extracted data only — never the reference profile.
 */
export interface DocumentExtractionResponse {
  document_id: string
  processing_status: ProcessingStatus
  extraction_status: ExtractionStatus | null
  model_name: string | null
  patient_name: string | null
  cnic: string | null
  date_of_birth: string | null
  report_date: string | null
  laboratory_reference: string | null
  str_profile: Record<string, number[]> | null
  extracted_marker_count: number
  cnic_consistency: ConsistencyStatus | null
  name_consistency: ConsistencyStatus | null
  validation_note: string | null
  extracted_at: string | null
}

// --- Step 8: Verification Decision Engine -------------------------------------------

export type DecisionOutcome = 'VERIFIED' | 'REVIEW_REQUIRED' | 'MISMATCH'

export type ConsistencyLevel = 'CONSISTENT' | 'INCONSISTENT' | 'NOT_DETECTED'

/** Response contract of POST/GET /api/v1/verifications/{id}/decision */
export interface DecisionResponse {
  verification_id: string
  decision: DecisionOutcome
  evidence_score: number
  dna_classification: string | null
  dna_match_percentage: number | null
  identity_consistency: ConsistencyLevel
  document_consistency: ConsistencyLevel
  explanation: string
  created_at: string
  updated_at: string
}

// --- Step 9: Verification Report & Audit Trail ---------------------------------

/** Append-only audit event types recorded by the backend services. */
export type AuditEventType =
  | 'CASE_CREATED'
  | 'DOCUMENT_UPLOADED'
  | 'DOCUMENT_PROCESSED'
  | 'DNA_COMPARED'
  | 'DECISION_GENERATED'
  | 'REPORT_GENERATED'

/** Safe identity summary of the report header. */
export interface ReportIdentity {
  cnic: string
  name: string
  father_name: string
  date_of_birth: string
  gender: string
  identity_status: string
}

/** Document metadata only - the API never sends storage paths. */
export interface ReportDocumentSection {
  available: boolean
  message: string | null
  document_count: number
  document_id: string | null
  original_filename: string | null
  document_type: DocumentType | null
  content_type: string | null
  file_size: number | null
  processing_status: ProcessingStatus | null
  uploaded_by: string | null
  uploaded_at: string | null
}

/** AI extraction summary, always labelled as AI output. */
export interface ReportExtractionSection {
  available: boolean
  message: string | null
  label: string
  extraction_status: ExtractionStatus | null
  model_name: string | null
  extracted_name: string | null
  extracted_cnic: string | null
  cnic_consistency: ConsistencyStatus | null
  name_consistency: ConsistencyStatus | null
  identity_consistency: ConsistencyLevel | null
  extracted_marker_count: number
  validation_note: string | null
  extracted_at: string | null
}

/** Aggregate STR result - counts and percentages, never allele values. */
export interface ReportDnaSection {
  available: boolean
  message: string | null
  engine_note: string
  classification: ComparisonClassification | null
  match_percentage: number | null
  total_markers: number | null
  matched_markers: number | null
  mismatched_markers: number | null
  missing_markers: number | null
  invalid_markers: number | null
  compared_at: string | null
}

/** Prototype Evidence Score breakdown (70 / 20 / 10). */
export interface ReportEvidenceSection {
  available: boolean
  message: string | null
  score_label: string
  score_note: string
  dna_score: number
  identity_score: number
  document_score: number
  total_score: number
  max_score: number
  identity_consistency: ConsistencyLevel | null
  document_consistency: ConsistencyLevel | null
  dna_classification: string | null
  dna_match_percentage: number | null
}

/** Final deterministic decision plus the engine's own explanation. */
export interface ReportDecisionSection {
  available: boolean
  message: string | null
  decision: DecisionOutcome | null
  explanation: string | null
  decided_at: string | null
}

/** One audit timeline entry: when, what, who. */
export interface ReportAuditEvent {
  timestamp: string
  event_type: AuditEventType
  event: string
  description: string
  actor: string
}

/** Response contract of GET /api/v1/verifications/{id}/report. */
export interface VerificationReport {
  verification_id: string
  status: CaseStatus
  generated_at: string
  identity: ReportIdentity
  document: ReportDocumentSection
  ai_extraction: ReportExtractionSection
  dna_analysis: ReportDnaSection
  evidence: ReportEvidenceSection
  decision: ReportDecisionSection
  audit_timeline: ReportAuditEvent[]
  disclaimer: string
}
