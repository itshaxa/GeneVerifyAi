# GeneVerify AI — Architecture

Status: **Step 13 — Final submission and release readiness — complete**. This
document describes the target architecture and marks what exists today versus what is
added in later stages. Step 12 added no new component: it verified the existing ones
end to end (see §11 for the verification record). Step 13 changed no component either —
it re-verified the whole system as a submission, including a recovery pass after an
unexpected system shutdown (see §12).

## 1. System Overview

```
┌─────────────────────┐         HTTPS/JSON          ┌──────────────────────────────┐
│  React + TS + Vite  │ ──────────────────────────► │  FastAPI backend             │
│  Tailwind CSS       │ ◄────────────────────────── │  ├── api/      (routes)      │
│  (frontend/)        │                             │  ├── services/ (logic)       │
└─────────────────────┘                             │  │    ├── str_engine (pure)  │
                                                    │  │    └── ai/ (Qwen seam)    │
                                                    │  ├── models/ + schemas/      │
                                                    │  └── database/ (SQLAlchemy)  │
                                                    └──────────────┬───────────────┘
                                                                   │
                                                    SQLite (now) → managed DB (later)
                                                                   │
                                                    Alibaba Cloud Qwen (advisory:
                                                    document extraction only)
```

Key invariant: **decisions are deterministic**. The STR engine and verification engine
produce the VERIFIED / REVIEW_REQUIRED / MISMATCH outcome, the score and the written
explanation. AI takes part only in reading fields out of an uploaded document.

## 2. Frontend (`frontend/`)

| Layer | Location | Responsibility |
| --- | --- | --- |
| Pages | `src/pages/` | Route-level screens (route map below) |
| Layouts | `src/layouts/AppLayout.tsx` | Shared chrome: header, primary nav, mobile menu, footer |
| Components | `src/components/` | Presentational pieces: badges, pipeline, section cards, state blocks, icons |
| Services | `src/services/` | Typed API clients; the only place that talks to the backend |
| Hooks | `src/hooks/` | `useCaseOverview`, `useVerificationReport`, `useHealthCheck` |
| Types | `src/types/api.ts` | API contract types mirroring backend Pydantic schemas |
| Utils | `src/utils/` | `format.ts` (UTC-aware dates), `errorMessage.ts` (safe messages), `reportFormat.ts` |
| Context | `src/context/AuthContext.tsx` | Session state |
| Assets | `src/assets/` | Static assets |

Stack: React 19.1 + TypeScript 5.8 (`strict`, `noUnusedLocals`,
`verbatimModuleSyntax`) + Vite 6 + Tailwind CSS v4 in CSS-first mode (`@theme` in
`src/index.css`; there is no `tailwind.config.js`), routed with `react-router-dom` 7.
Dev servers talk to the API through the `CORS_ORIGINS` allow-list in `backend/.env`
(`http://localhost:5173` by default, so a Vite instance started on any other port is
rejected by the browser until that setting is adjusted — a deployment concern, not an
application one).

- All HTTP access goes through `services/apiClient.ts` (typed `apiFetch` + `ApiError`),
  so error handling, base-URL resolution and the bearer token stay consistent. The base
  URL resolves in one place (`resolveApiBaseUrl`): `VITE_API_BASE_URL` when set, else
  same-origin `/api/v1` in a production build, else `http://localhost:8000/api/v1` in
  development — so no production bundle depends on a localhost address. On any `401`
  the client clears the session and redirects to `/login`.
- Authentication state lives in `src/context/AuthContext.tsx`; tokens are handled
  only by `services/tokenStorage.ts` + `services/authService.ts`.
- Visual identity: premium white/light-gray surfaces with green accents, defined as
  Tailwind `brand-*` theme tokens in `src/index.css`.
- Public surface is the login page only; every app page renders inside the
  `ProtectedRoute` guard, which Step 10 left unchanged.
- Report views are read-only projections: `VerificationReportSection` (summary
  card) and `VerificationReportPage` render exactly what `GET .../report`
  returned and never recompute a score, classification or verdict client-side.

### 2.1 Route map (Step 10)

| Route | Page | Purpose |
| --- | --- | --- |
| `/login` | `LoginPage` | Only public route |
| `/` | `DashboardPage` | Command Center: overview cards, quick actions, pipeline, recent work |
| `/verify` | `VerificationWorkspacePage` | CNIC entry, identity confirmation, case creation, next step |
| `/verifications` | `VerificationCasesPage` | Case history table |
| `/verifications/:verificationId` | `VerificationCaseDetailPage` | Case header → pipeline → documents → extraction → DNA → assessment → audit trail → report |
| `/verifications/:verificationId/report` | `VerificationReportPage` | Nine-section report + prominent PDF download |
| `/reports` | `ReportsPage` | Report library over the existing case/decision data |
| `/lookup` | `IdentityLookupPage` | Original single-record lookup (kept) |
| `/overview` | `HomePage` | Project positioning + backend health |

`AppLayout` exposes **Dashboard · Verify Identity · My Cases · Reports** plus the
user's name, role and logout. Below 640 px the links collapse into a hamburger menu
that is keyboard operable (`aria-expanded`/`aria-controls`, Escape closes and restores
focus, navigating closes it) and no supported width scrolls horizontally.

### 2.2 Data flow — one owner per concern

| Concern | Owner | Calls |
| --- | --- | --- |
| Overview / dashboard / report library | `hooks/useCaseOverview.ts` | `GET /verifications` + bounded `GET /verifications/{id}/decision` |
| A case's report, audit trail and PDF | `hooks/useVerificationReport.ts` | `GET .../report`, `GET .../report/download` |
| Case list actions, upload, extraction, comparison, decision | page-local handlers in `services/*` | unchanged Step 4–9 endpoints |

- The backend has no aggregate statistics endpoint, and `VERIFIED` and `MISMATCH`
  both map a case to `completed`, so outcome counts come from stored decisions read
  per case — bounded to the 40 most recent eligible cases, with
  `decisionCoverage.skipped` surfaced so the UI states its own basis instead of
  estimating. A decision `404` means "none recorded yet", never an error.
- `useVerificationReport` replaced the duplicated report fetches that the summary
  card and the report page each issued: a page loads the report once and hands the
  same payload to the pipeline, the audit timeline and the report preview.
- The eight-stage `VerificationPipeline` derives its state purely from the report
  payload's per-stage `available`/`message` fields (stage 08 from a
  `REPORT_GENERATED` audit event) — no backend rule is re-implemented in React.

### 2.3 Presentation primitives

- `index.css` defines the tokens and component classes (`gv-card`, `gv-glass`,
  `gv-badge`, `gv-btn` variants, `gv-skeleton`, staggered entrances) plus exactly six
  animation tokens (`gv-fade-up`, `gv-fade-in`, `gv-pop`, `gv-menu`, `gv-shimmer`,
  `gv-ping`), all suppressed under `@media (prefers-reduced-motion: reduce)`.
  No animation or component library was added; `components/Icons.tsx` holds
  hand-written inline SVG icons marked `aria-hidden`.
- `components/StateBlocks.tsx` standardizes every asynchronous UI state:
  `Skeleton`, `LoadingBlock`, `EmptyState`, `ErrorState`, `InfoNotice`, `ScrollHint`,
  `SectionCard`, `Field`. Expected outcomes (unknown CNIC, incomplete CNIC, case with
  no decision) render as neutral notices, not as failures, and no state can leak a
  stack trace, database error, path, API key, JWT, password hash or raw provider
  response.
- `CaseStatusBadge` and `DecisionBadge` display the backend enum values verbatim and
  pair colour with an icon and text, so meaning never rests on colour alone.
- `utils/format.ts` treats the API's naive timestamps as UTC (the models use
  `server_default=func.now()`), so absolute and relative times agree.

## 3. Backend (`backend/`)

Layered strictly; **routes never contain business logic**.

| Layer | Location | Responsibility |
| --- | --- | --- |
| API routes | `app/api/routes/` | HTTP contracts, status codes, delegation to services |
| Router | `app/api/router.py` | Aggregates routers under `/api/v1` |
| Auth deps | `app/api/deps.py` | `get_current_user`, `require_authenticated_user`, `require_role(...)` |
| Services | `app/services/` | All business logic: STR engine, verification, identity, documents, AI, audit trail, reports/PDF, auth/security |
| ORM models | `app/models/` | SQLAlchemy persistence models |
| Schemas | `app/schemas/` | Pydantic request/response contracts |
| Database | `app/database/` | Engine, session management, ORM base |
| Core | `app/core/` | Settings (env-driven), logging |
| Entry point | `app/main.py` | App factory, CORS, production startup guards, uniform error handlers |
| Deployment entry | `run.py` | `HOST`/`PORT`-aware uvicorn launcher (`python run.py` → `app.main:app`) |
| Containers | `Dockerfile`, `.dockerignore` | Optional lean runtime image (env-configured, non-root, mounted `/srv/geneverify/data` for DB + documents) |

Cross-cutting decisions already in place:
- **Configuration**: env vars / `.env` only (pydantic-settings); no hardcoded secrets.
  Real environment variables take precedence over `.env`, which is what a platform's
  secret/env configuration relies on.
- **Production guards** (Step 11): `create_app()` refuses `APP_ENV=production` while the
  insecure development `JWT_SECRET_KEY` placeholder is in use or `DEBUG` is enabled, and
  warns (without failing) about loopback CORS origins and `AI_PROVIDER=mock`.
  Non-production environments keep the previous behaviour.
- **Dependencies**: `requirements.txt` is runtime-only; `requirements-dev.txt`
  (`-r requirements.txt` + `pytest` + `httpx`) is for the test suite. `httpx` is listed
  explicitly because `fastapi.testclient` needs it — the previous manifest listed the
  unrelated `httpx2` package, which installs an `httpx2` module and never provided it.
- **Error handling**: uniform `ErrorResponse` envelope for HTTP errors, validation
  errors and unhandled exceptions.
- **Logging**: single structured console format, level from `LOG_LEVEL`.
- **Security posture**: JWT authentication (Argon2id password hashing, HS256 access
  tokens with expiry), active-user checks, generic anti-enumeration error messages,
  strict input validation via Pydantic, file type/size validation for uploads,
  CORS allowlist from configuration. See §4.3 for the authentication design.

## 4. Database

- **Now**: SQLite via SQLAlchemy 2.x (`DATABASE_URL`).
- **Later**: swap to managed PostgreSQL/RDS on Alibaba Cloud — only `DATABASE_URL`
  changes, no code changes.
- Schema initialization is non-destructive: at startup a `create_all` ensures tables
  exist and never drops data. Demo data is written only by the explicit seed command.
- Deployment readiness (Step 11): the parent directory of a file-based `DATABASE_URL` is
  created if missing (an empty mounted volume such as `/data` therefore works), and
  `PRAGMA foreign_keys=ON` is issued on every SQLite connection so the `ON DELETE
  CASCADE` rules actually fire. Deployment must never delete or recreate the database
  file; no migration tooling or destructive reset exists.
- Remaining planned entity groups (later stages): verification sessions,
  verification history, analytics snapshots.

### 4.1 Data model (Steps 2, 4, 5, 6, 7, 8 & 9)

All identity and DNA records in this prototype are synthetic demonstration data.

```
users 1 ──── N verification_cases 1 ──── N dna_comparison_results
     │                 │                        │
     │                 │                        1
     │                 ├──── N verification_documents 1 ──── 1 document_extractions
     │                 │
     │                 ├──── 1 verification_decisions
     │                 ├──── N verification_audit_events (actor → users)
     │                 N
     │                 │
     │        1 identity_records 1 ──── 1 dna_profiles
     └── verification_documents.uploaded_by_user_id ──┘
```

| Table | Key columns | Notes |
| --- | --- | --- |
| `identity_records` | `id`, `cnic` (unique, indexed), `name`, `father_name`, `date_of_birth`, `gender`, `address`, `photo_reference`, `status`, `created_at`, `updated_at` | Synthetic demo records only; `status` ∈ active / inactive / under_review |
| `dna_profiles` | `id`, `identity_record_id` (unique FK → identity_records.id), `profile_code` (unique), `markers` (JSON), `created_at`, `updated_at` | One-to-one with identity; `markers` = `{"D3S1358": [15, 16], ...}` for all 20 panel markers, two alleles each |
| `users` | `id`, `username` (unique, indexed), `password_hash`, `role`, `is_active`, timestamps | See §4.3 |
| `verification_cases` | `id`, `verification_id` (unique, indexed), `identity_record_id` (FK → identity_records), `created_by_user_id` (FK → users), `status`, `created_at`, `updated_at` | See §4.4; identity data is referenced, never duplicated |
| `dna_comparison_results` | `id`, `verification_case_id` (FK → verification_cases), `classification`, `total_markers`, `matched_markers`, `mismatched_markers`, `missing_markers`, `invalid_markers`, `match_percentage`, `marker_results` (JSON), `submitted_markers` (JSON), `created_at` | See §4.5; one row per comparison run. The submitted profile is kept as the prototype audit trail; reference DNA is NOT duplicated here |
| `verification_documents` | `id`, `document_id` (unique, indexed), `verification_case_id` (FK → verification_cases), `original_filename`, `stored_filename`, `content_type`, `file_size`, `storage_path`, `document_type`, `processing_status`, `uploaded_by_user_id` (FK → users), `created_at`, `updated_at` | See §4.6; metadata only — file binaries live on the filesystem, never in SQLite |
| `document_extractions` | `id`, `verification_document_id` (unique FK → verification_documents, CASCADE), `extraction_status`, `extracted_identity_data` (JSON), `extracted_str_profile` (JSON), `extracted_marker_count`, `model_name`, `validation_note`, `created_at`, `updated_at` | See §4.7; one row per document (1:1) — audit-grade AI extraction record, no API keys, no raw provider payloads |
| `verification_decisions` | `id`, `verification_case_id` (unique FK → verification_cases, CASCADE), `dna_classification`, `dna_match_percentage`, `identity_consistency`, `document_consistency`, `evidence_score`, `decision`, `explanation`, `created_at`, `updated_at` | See §4.8; one decision per case (upserted) — transparent evidence score, deterministic decision, no raw DNA, no AI inference |
| `verification_audit_events` | `id`, `verification_case_id` (FK → verification_cases, CASCADE, indexed), `actor_user_id` (FK → users, RESTRICT, indexed), `event_type`, `event_description`, `created_at` (indexed) | See §4.9; append-only trail of completed actions — safe summary text only, no DNA, no credentials, no paths |

STR marker representation: structured JSON validated against the panel defined in
`app/services/str_engine/panel.py` (20 markers, exactly two positive numeric alleles
per marker). This exact structure is what the deterministic STR engine (§6) consumes.

Seeding (`python -m app.database.seed`):
- Deterministic: fixed RNG seed `20260828`; identical dataset in every environment.
- Idempotent: records whose CNIC already exists are skipped — no duplicates on rerun.
- 120 generated records + 3 demo records (match / mismatch / manual-review cases),
  all using the never-issued `99900` demo CNIC prefix.

### 4.2 Data access security

- **No browsing**: there is no `GET /identities`, `GET /identity/all`, or export
  endpoint — and there never will be one. Tests assert this invariant.
- **Single record only**: `GET /api/v1/identity/{cnic}` requires a bearer token,
  validates the CNIC format, queries the indexed unique CNIC, and returns exactly
  one safe record (401 unauthenticated, 404 when absent, 422 when malformed).
- **DNA profiles stay internal**: the lookup response schema
  (`IdentityLookupResponse`) contains identity fields only. Reference profiles are
  reachable exclusively through `services/dna_service.py` for the future
  verification workflow.

### 4.3 Authentication (Step 3)

```
users table ── Argon2id hash ──► auth_service.authenticate_user()
                                        │ success
                                        ▼
                       security_service.create_access_token(user)
                       (JWT: sub/username/role/iat/exp, HS256)
                                        │
                       POST /auth/login returns { access_token, user }
                                        │
             every protected route: Depends(get_current_user) → active User
```

| Aspect | Design |
| --- | --- |
| `users` table | `id`, `username` (unique, indexed), `password_hash`, `role` (enum: admin/officer), `is_active`, timestamps |
| Password hashing | Argon2id via `argon2-cffi`; plaintext never stored, returned or logged |
| Tokens | Short-lived HMAC JWT (PyJWT). Config from env: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`. Claims are identity-only — never personal/DNA data |
| Login | `POST /api/v1/auth/login` → 401 with a uniform message for wrong password, unknown user, or inactive user (no enumeration) |
| Session check | `GET /api/v1/auth/me` returns `UserPublic` (id/username/role/is_active — no hash) |
| Logout | Stateless: `POST /api/v1/auth/logout` acknowledges; the client discards the token. Upgrade path: server-side sessions/cookies |
| Demo user | `python -m app.database.seed_users` (idempotent). Username `admin`; password read from `DEMO_ADMIN_PASSWORD` env, hashed before storage. Synthetic hackathon credential — must be replaced before production |
| Production guard | `create_app()` refuses to boot in `APP_ENV=production` with the insecure dev JWT secret |

Future verification, DNA, document, report, analytics and admin endpoints are
protected by adding the same dependencies — `Depends(get_current_user)` or
`Depends(require_role(UserRole.ADMIN))`.

### 4.4 Verification cases (Step 4)

The case-management foundation. A `verification_cases` row is the future
container for submitted DNA, STR comparison results, documents, AI analysis,
score, risk assessment, final result and audit information — none of which
exist yet.

- **Verification ID** (`GV-YYYY-NNNNNN`): generated by
  `verification_case_service.VerificationIdGenerator` (per-year sequential,
  zero-padded, unique-constrained, IntegrityError-retried). Human-readable for
  reports; never the internal PK; never derived from the CNIC.
- **Status lifecycle:** `draft` (default on creation) → `in_progress` /
  `completed` / `review_required` / `cancelled`. The service supports status
  updates; transition rules arrive with the verification engine.
- **Ownership / access:** creator comes from the JWT only. Officers access
  only their own cases; admins can review all cases (audit); foreign cases
  respond `404` so existence is not disclosed. Implemented in the service
  layer (`get_case`, `list_cases_for_user`), so routes stay thin.
- **Response hygiene:** `VerificationCaseResponse` embeds a bounded
  `CaseIdentitySummary` (no address, no DNA). STR profiles remain reachable
  only through the internal `dna_service`.
- **Future connections:** document metadata, Qwen findings, scores and reports
  (verification session entities) will attach to a case via
  `verification_cases.id`, alongside the DNA comparison results (§4.5).

### 4.5 DNA comparison results (Step 5)

Each deterministic comparison for a case is persisted as a
`dna_comparison_results` row:

- Aggregate counts (`total/matched/mismatched/missing/invalid`),
  `match_percentage`, classification, full per-marker breakdown (JSON) and the
  submitted profile exactly as received.
- Why store the submitted profile: until document/lab-report ingestion exists,
  the stored copy is the only audit trail of what evidence was compared. It is
  internal-only — never served through case list/detail responses.
- Reference DNA is never copied here; it stays reachable only through
  `dna_service` (case → identity → dna_profile).
- Re-runs are allowed and each run is kept (auditability). A successful
  comparison moves a `draft` case to `in_progress`.

### 4.6 Verification documents (Step 6)

Each upload to a case becomes a `verification_documents` row plus one file on
disk. Files are **never stored in SQLite**: binaries are large, immutable and
better served by a filesystem/object store — keeping them out of the database
avoids bloat, keeps backups small and matches the future Alibaba Cloud design
(swap the local storage service for OSS without touching the model).

- **Document ID** (`GVD-YYYY-NNNNNN`): generated by
  `document_service.DocumentIdGenerator` (per-year sequential, unique,
  IntegrityError-retried). Never derived from the CNIC or filename; the
  internal PK is never exposed.
- **Secure storage** (`document_storage_service`): root from
  `DOCUMENT_STORAGE_PATH` (gitignored, outside source trees, never mounted
  statically). Stored filenames are server-generated uuid hex + extension; the
  user-supplied name survives only as sanitized display metadata. Every
  save/resolve/delete re-resolves inside the root and refuses any path
  traversal — crafted metadata cannot escape the directory.
- **Validation:** extension (`.pdf/.png/.jpg/.jpeg`), declared MIME type,
  size (`MAX_DOCUMENT_SIZE_MB`, default 10 MB → 413) and magic-byte
  signatures — spoofed content is rejected with 422 and never persisted.
- **Ownership:** uploads require an accessible case (Step 4 rules); the
  uploader is always the authenticated user. Officers see only their own
  cases' documents; admins all; foreign cases/documents answer 404. Responses
  expose metadata only — no storage paths, no stored filenames, no DNA.
- **Processing status:** documents start `UPLOADED`; Step 7 moves them
  through `PROCESSING` → `PROCESSED`/`FAILED` (§4.7) and feeds the extracted
  STR profile into the deterministic engine (§6) — AI output never bypasses
  the engine.

### 4.7 Document extractions (Step 7)

The AI extraction pipeline (`document_extraction_service`) persists one
`document_extractions` row per document (unique FK, cascade on document
deletion — enforced at the database level: SQLite connections enable
`PRAGMA foreign_keys=ON`, without which the cascade would silently never
fire):

- **Flow:** auth/ownership → metadata → file-on-disk check → `PROCESSING` →
  provider extraction → strict Pydantic validation (`schemas/extraction.py`)
  → persisted extraction → `PROCESSED`. Failures transition to `FAILED` and
  always record an audit row with a user-safe `validation_note`.
- **Strict schema:** AI output is never repaired. Unknown markers,
  non-numeric/null alleles, wrong allele counts, out-of-range values and
  arbitrary extra fields raise controlled failures. Markers/ranges come from
  the canonical panel only (`str_engine/panel.py`).
- **Consistency checks:** extracted CNIC/name are compared with the case
  identity using deterministic normalization (digit-only CNICs; sorted,
  case/whitespace-insensitive names) → `CONSISTENT` / `INCONSISTENT` /
  `NOT_DETECTED`. These are *document identity-field consistency* signals —
  never identity verification, and the AI never interprets them.
- **Auditability:** document id, processing status, model name, extraction
  timestamp, extracted marker count and validation outcome are all stored.
  No API keys, raw provider payloads or storage paths are persisted.
- **Cost control:** processing is triggered only by an explicit operator
  action; `PROCESSED` documents reject re-processing (409), and stored
  extractions are served without new AI calls.

### 4.8 Verification decisions (Step 8)

The verification decision engine (`decision_service.py`) produces one
`verification_decisions` row per case (unique FK, upserted on re-run):

- **Inputs:** the latest DNA comparison (Step 5) and the latest successful
  document extraction (Step 7). The decision never triggers AI — it reads
  already-persisted evidence.
- **Prototype Evidence Score:** deterministic weighting (DNA 70, Identity
  consistency 20, Document consistency 10; total 100). The score is a
  transparent application-level decision aid, NOT a forensic probability.
- **Decision:** explicit rules map classification + evidence availability to
  `VERIFIED` / `REVIEW_REQUIRED` / `MISMATCH`. The numeric score never
  determines the outcome alone.
- **Explanation:** deterministic natural-language summary generated from
  actual evidence values. Never invents facts. No LLM used.
- **Case status integration:** the engine updates the case status
  (`completed` or `review_required`) based on the decision outcome.
- **Security boundary:** the response exposes only safe summary fields
  (classification, percentage, consistency levels, score, explanation,
  timestamps) — never raw DNA profiles, reference alleles, password hashes,
  API keys, JWTs, filesystem paths or raw provider responses.

### 4.9 Verification audit events (Step 9)

`app/models/verification_audit.py` + `app/services/audit_service.py` give every
case an append-only history of what actually happened to it.

- **Event types** (`AuditEventType`, stored as a `VARCHAR(32)` enum so SQLite
  needs no DDL migration when a type is added later):
  `CASE_CREATED` · `DOCUMENT_UPLOADED` · `DOCUMENT_PROCESSED` ·
  `DNA_COMPARED` · `DECISION_GENERATED` · `REPORT_GENERATED` — one per
  meaningful completed action of Steps 4–9.
- **Recording:** `record_event(db, case, actor, event_type, description)` is
  called by the *owning service* immediately after its business transaction
  commits (`verification_case_service`, `document_service`,
  `document_extraction_service`, `dna_comparison_service`, `decision_service`,
  `report_service`). Routes stay thin and no client can name an actor or forge
  an event: the actor is always the authenticated `User` resolved by the JWT
  dependency, and there is no write endpoint for events at all.
- **Reads never write:** `GET` case/document/extraction/decision/report requests
  add nothing, so refreshing a page cannot inflate the timeline. Failed
  operations add nothing either — an event means the action succeeded.
- **Durability:** `audit_service` imports only ORM models, never another
  service, so it cannot form an import cycle; a recording failure is logged and
  swallowed rather than rolling back a completed operation.
- **Content safety:** `event_description` is a ≤255-character summary built from
  identifiers and aggregate results (`GVD-2026-000007 uploaded (DNA Report)`,
  `EXACT_MATCH, 100.0%`, `VERIFIED (prototype evidence score 100/100)`). It
  never contains passwords, JWTs, API keys, raw STR markers/alleles, document
  contents, filesystem/storage paths or raw provider responses — asserted by
  tests.
- **Ordering:** `get_case_events` returns `ORDER BY created_at, id` — the DB
  timestamp has only second resolution, so `id` is the deterministic tiebreak.
- **Retention:** case deletion cascades the trail (evidence belongs to its
  case); `actor_user_id` is `RESTRICT` so an actor can never be dropped out from
  under a historical event.

## 5. AI Layer (Alibaba Cloud Qwen)

Isolated in `app/services/ai/` behind abstract interfaces (`base.py`) —
Qwen-specific code lives nowhere else (not in routes, not in the STR engine,
not in models, not in the frontend):

- `DocumentIntelligenceService` — extracts structured fields from DNA reports and
  identity documents (`extract_dna_report` returns identity fields + `str_profile`).
- `VerificationExplainerService` — writes natural-language explanations of findings
  (interface reserved for a later stage).
- `QwenDocumentIntelligenceService` (`qwen.py`) — calls Qwen through the
  OpenAI-compatible chat-completions endpoint (DashScope compatible mode).
  The document is sent as a base64 data URL so Qwen-VL models read PDFs and
  images directly — no local OCR pipeline. The extraction prompt is
  extraction-only and anti-hallucination (no guessing, no invented alleles,
  canonical markers only, JSON-only answer) and declares the document
  UNTRUSTED INPUT to resist prompt injection. All provider errors become
  user-safe `AIProviderError` messages (no keys, no stack traces).
- `MockDocumentIntelligenceService` (`mock.py`) — deterministic,
  network-free provider for development and automated tests. It reads the
  `NAME | allele, allele` table printed in the document itself (via
  `document_text.py`, which parses the `(text) Tj` operators of uncompressed PDF
  output) and reports those markers, so a report that deliberately disagrees with
  the registered profile can be exercised end-to-end without an API key. When the
  text is unreadable — compressed streams, scans, or the bare byte payloads the
  test suite uploads — it falls back to the case's reference profile from
  `context`, the original "perfectly scanned report" simulation. Identity fields
  always come from `context`. The behaviour markers `GV-FAIL`, `GV-BADJSON` and
  `GV-BADSTR` are matched against the raw file bytes and short-circuit all of
  that, while `GV-PARTIAL` subtracts two markers from whatever profile was read.
  Either way the provider only produces a candidate profile: the deterministic
  STR engine compares it.
- `create_document_intelligence_service` (`factory.py`) — selects the
  provider from `AI_PROVIDER` (`qwen` | `mock`). `qwen` without
  `QWEN_API_KEY` → "AI provider is not configured."; the mock is refused in
  `APP_ENV=production` (no silent mock in production). The app always boots.

Rules:
1. AI output is **extraction/explanation only**: the AI is never asked
   whether a profile matches. Extracted fields are re-validated by
   deterministic rules; the deterministic STR engine (§6) is the only
   component that compares DNA profiles.
2. Providers are injected via a FastAPI dependency
   (`get_document_intelligence_service`), so routes depend on the interface
   only and tests inject the mock.
3. Qwen credentials come from environment configuration only
   (`QWEN_API_KEY`, `QWEN_MODEL`, `QWEN_BASE_URL`, `QWEN_TIMEOUT_SECONDS`).

## 6. Deterministic STR Engine (Step 5 — implemented)

Package: `app/services/str_engine/`.

- `panel.py` — the canonical 20-marker demonstration panel, per-marker allele
  ranges, and storage-time marker validation. Single source of truth; no second
  marker list exists anywhere.
- `comparison.py` — pure comparison logic: `compare_profiles(reference,
  submitted)` → `ComparisonResult` (classification + `ComparisonSummary` +
  per-marker `MarkerResult`s). `validate_profile(...)` performs strict,
  structured validation of both profiles before any comparison.

Guarantees (all covered by tests):
- Pure function of its inputs: same two profiles ⇒ same result, every time.
  No RNG, no clock dependence, no I/O — fully offline.
- Zero imports from `app/services/ai/` — an LLM never decides whether two
  profiles match. AI's only live role is document extraction (§5); the explanation
  shown with a decision is built deterministically by the decision engine.
- Allele order never matters: pairs are compared as sorted multisets, so
  `[15, 16]` vs `[16, 15]` is a MATCH; duplicate alleles (`[15, 15]`) are valid
  homozygous calls.
- Missing data is explicit, never coerced into mismatches:
  `MISSING_SUBMITTED` / `MISSING_REFERENCE` marker statuses, reported in the
  summary separately from `MATCH` / `MISMATCH` / `INVALID`.
- Invalid data is never repaired: empty profiles, unexpected/malformed marker
  names, wrong allele counts, non-numeric/null alleles and out-of-range values
  raise `StrProfileValidationError` with every detected issue.

Overall classification (documented, deterministic, tested):

| Classification | Rule |
| --- | --- |
| `EXACT_MATCH` | all 20 panel markers match |
| `PARTIAL_MATCH` | ≥1 marker matches but not all (incl. missing submitted markers) — **never** an identity confirmation |
| `NO_MATCH` | zero markers match |
| `INVALID` | comparison not evaluable |

`match_percentage` = matched ÷ 20 × 100 (one decimal). It is a marker count
ratio — explicitly **not** a forensic probability and not legally valid
identity confirmation.

### 6.1 Case integration

```
authenticated user → POST /verifications/{id}/dna/compare {"submitted_profile": ...}
   → case lookup (Step 4 ownership; foreign case ⇒ 404)
   → reference DNA internally (dna_service: case → identity → dna_profile)
   → submitted profile validated (422 with structured issues)
   → deterministic comparison → persist dna_comparison_results row
   → structured result (classification, summary, per-marker table)
```

Security boundary: the request model forbids extra fields, so a client-supplied
`reference_profile` is rejected with 422 — the reference is always resolved
server-side. No bulk DNA endpoints exist; the identity lookup still exposes no
DNA. Successful comparisons move `draft` cases to `in_progress`.

The frontend case detail page provides a simple DNA Analysis section:
structured STR profile input, `[Compare DNA]`, overall result, match
percentage, marker summary and a Marker/Reference/Submitted/Status table —
labelled conservatively ("STR profile consistent with reference profile", a
partial match never claims identity). The same page carries the DNA Document
section above it (§4.6/§4.7): the manual STR input is labelled "Manual/Test
STR Profile", while AI-extracted profiles flow through this exact same
endpoint via **[Compare With Registered DNA]** — one deterministic engine,
no duplicated comparison logic.

## 7. Verification Engine & Scoring (Step 8)

The verification decision engine (`app/services/decision_service.py`) combines
existing deterministic evidence into a transparent Prototype Evidence Score
and final decision:

```
DNA comparison (Step 5) ─────────┐
                                  ├─► Decision Engine (deterministic) ─► score + decision
Document extraction (Step 7) ────┘                                             │
                                                                               ▼
                                                     deterministic explanation builder
```

- **Score weighting:** DNA 70 + Identity 20 + Document 10 = 100 points.
  - EXACT_MATCH: DNA = 70/70
  - PARTIAL_MATCH: proportional, capped at 60 (never auto-VERIFIED)
  - NO_MATCH / INVALID: DNA = 0
- **Decision rules:** classification-driven; the numeric score never determines
  the outcome alone. The STR engine is authoritative for DNA; the decision
  engine never overrides it.
- **Case status update:** VERIFIED → completed, MISMATCH → completed,
  REVIEW_REQUIRED → review_required. No complex state machine.
- **Explanation:** deterministic text built from actual evidence fields.
  Never invents facts. No LLM is used.
- **Security:** response exposes only safe summary fields — never raw DNA
  profiles, reference alleles, passwords, API keys or filesystem paths.

## 8. Verification Report & PDF (Step 9)

The report layer (`app/schemas/report.py`, `app/services/report_service.py`,
`app/services/report_pdf_service.py`) turns a case's existing evidence into a
professional, self-consistent document:

```
verification_cases
  ├─ identity_records                          ┐
  ├─ verification_documents (metadata only)    │
  ├─ document_extractions                      ├─► report_service ─┬─► VerificationReport (JSON)
  ├─ dna_comparison_results (aggregates)       │                   └─► report_pdf_service ─► PDF
  ├─ verification_decisions                    │
  └─ verification_audit_events                 ┘
```

- **Read-only projection:** every section is copied from a row that already
  exists. The report never calls the STR engine, never re-scores, never
  re-decides and never invokes an AI provider — so the JSON, the PDF and the
  case screens can never disagree with the stored evidence.
- **Nine sections** (fixed contract, mirrored 1:1 by the frontend types):
  header (`verification_id`, `status`, `generated_at`) · `identity` ·
  `document` · `ai_extraction` · `dna_analysis` · `evidence` · `decision` ·
  `audit_timeline` · `disclaimer`.
- **Mandated wording** lives in `schemas/report.py` as single-source constants:
  `AI_EXTRACTION_LABEL` ("AI-extracted information — validated before use."),
  `DNA_ENGINE_NOTE` (deterministic STR matching engine), `EVIDENCE_SCORE_LABEL`
  /`EVIDENCE_SCORE_NOTE` (prototype score, not a forensic probability) and
  `REPORT_DISCLAIMER` (synthetic-data, non-forensic statement).
- **Missing evidence is explicit:** each section carries `available` + `message`,
  so an incomplete case renders "No document submitted.", "Document has not been
  processed.", "DNA comparison not available." or "Verification decision not
  available." — a report is always produced, never a 500 and never a fabricated
  value. The subject document is the newest `PROCESSED` upload, else the newest
  upload.
- **Privacy by schema:** the Pydantic section models simply have nowhere to put
  allele values, storage paths, password hashes or provider payloads; the DNA
  section carries classification, percentage and counts only. Tests assert the
  serialized JSON and the extracted PDF text contain no marker names, no alleles,
  no paths, no hashes and no tokens.
- **PDF rendering** (`fpdf2`, pure Python, no browser/JS/COM): A4 with margins,
  brand header (title + verification ID) and footer (prototype statement + page
  number), numbered section bars, label/value fields, coloured decision banner,
  score bars and a vertical audit timeline. It measures rows before drawing
  (`multi_cell(dry_run=True)`) so blocks break across pages cleanly; text passes
  through a latin-1 sanitizer because the core fonts are 8-bit, and only a
  filename's basename is ever printed. Output is deterministic for identical
  input data.
- **Auditing:** `generate_report_pdf` records `REPORT_GENERATED` and returns
  `(report, pdf_bytes, filename)`; `build_report` (the JSON route) records
  nothing. Download filename: `GeneVerify-Report-<VERIFICATION ID>.pdf`.
- **No backfill (known limitation):** the trail only ever holds what the service
  layer wrote from Step 9 onward, so cases created earlier legitimately render an
  empty timeline ("No audit events recorded.") until their next action — history
  is never reconstructed or inferred.
- **Access control:** both routes delegate to `verification_case_service.get_case`
  (Step 4 rules) and map its not-found error to the existing safe 404 — a foreign
  or unknown ID is indistinguishable, and `401` covers missing/invalid tokens.

## 9. Deployment (Step 11) and future Alibaba Cloud work

**Made ready in Step 11 (verified locally):**

- One-process target kept deliberately simple: browser → static frontend → HTTPS →
  FastAPI → SQLite → document storage, and FastAPI → Qwen. No Kubernetes, no
  microservices, no Redis/Celery, no queue, no object storage.
- `python run.py` (or `uvicorn app.main:app --host 0.0.0.0 --port $PORT`) honours the
  platform-injected `PORT`, binds all interfaces in production and loopback in
  development.
- Every deployment knob is an environment variable (see `backend/.env.example`); the
  app refuses to start in production with development secrets or debug mode on.
- Database and document-storage locations are configurable and their directories are
  created without touching existing data; `storage/` and `*.db` are gitignored.
- The frontend build takes its API URL from `VITE_API_BASE_URL` and otherwise defaults
  to same-origin `/api/v1` for a single-host reverse-proxy deployment.
- `/api/v1/health` stays unauthenticated and minimal for platform health checks.
- An optional `backend/Dockerfile` (`python:3.14-slim`, runtime deps only, non-root,
  mounted `/srv/geneverify/data` for the database and documents, no secrets baked in)
  exists for container hosting.

**Not done — no cloud resource was created, contacted or verified:**

- Actual deployment to ECS/SAE/Function Compute, TLS certificates, DNS and the reverse
  proxy in front of `dist/` + the API.
- Building/running the container image (no Docker engine on this machine).
- Serving `dist/` from OSS + CDN, and managed RDS PostgreSQL in place of SQLite.
- Storing `QWEN_API_KEY` in a cloud secret manager and pointing `AI_PROVIDER=qwen` at
  DashScope/Model Studio; the key must come from deployment environment configuration,
  never from code or a `VITE_*` variable.
- Object storage (OSS) for archived report copies is a later-stage concern — nothing
  writes report files; the PDF is generated locally by `fpdf2`.
- Managed/rotated operator accounts in place of the synthetic demo credentials.

Deliberately out of scope for a hackathon prototype: microservice decomposition,
Kubernetes, blockchain.

Step 13 re-read this section against reality and changed none of it: nothing in the
"Not done" list was performed. No cloud resource was created, contacted or verified, the
docker image is still unbuilt (no Docker engine on this machine), and no `QWEN_API_KEY`
exists anywhere in the project or its environment.

## 10. Development Stages

| Stage | Scope | Status |
| --- | --- | --- |
| 0 | Monorepo foundation, health endpoint, shell, docs | ✅ done |
| 1 | Synthetic identity dataset + DNA data layer + CNIC lookup | ✅ done |
| 2 | Auth (JWT) for operators, protected lookup, login UI | ✅ done |
| 3 | Verification case management (foundation) | ✅ done |
| 4 | Deterministic STR engine (profile comparison + case integration) | ✅ done |
| 5 | Secure document upload pipeline (storage foundation, no AI) | ✅ done |
| 6 | Qwen document intelligence (STR extraction) | ✅ done |
| 7 | Verification decision engine (scoring, rules, explanation, case status) | ✅ done |
| 8 | Verification report, audit trail and PDF download | ✅ done |
| 9 | Command Center, workflow presentation and final UI polish | ✅ done |
| 10 | Deployment & production readiness (config, guards, startup, build, docs) | ✅ done |
| 11 | Final integration, QA and hackathon demo readiness (verification only) | ✅ done |
| 12 | Final submission & release readiness: audit, security, integrity, demo and documentation verification (no code change) | ✅ done |
| 13 | Admin management of identity/DNA records, real cloud deployment | planned |

Stage numbers are zero-based, so a stage is the project-brief step number minus one
(stage 8 = Step 9, stage 9 = Step 10, stage 10 = Step 11, stage 11 = Step 12,
stage 12 = Step 13).

## 11. Step 12 Verification Record

Step 12 changed no engine, schema, route or rule. It exercised the existing pipeline
from both sides and recorded the result, so this section is the evidence base for the
demo rather than a description of new code.

| Layer | How it was verified | Result |
| --- | --- | --- |
| Pipeline stages 1–14 (CNIC → PDF) | Live HTTP battery against a running server over the existing synthetic cases: login, lookup, case read, document list/file, extraction, comparison, decision, audit, report, PDF | 92/92 checks passed |
| Write path | Performed through the UI in a browser (see the UI walkthrough row): case `GV-2026-000024` created, `demo-synthetic-dna-report.pdf` uploaded, extracted (20/20 markers), compared (`EXACT_MATCH`), decided (`VERIFIED` 100/100), reported and downloaded | 7 audit events, all stages recorded |
| Report semantics | Report payload compared with the stored decision for a VERIFIED, a REVIEW_REQUIRED and a MISMATCH case; section set and aggregate-only DNA block asserted | Matches stored decisions; no allele-level leakage |
| PDF | `%PDF-` header, non-zero length, embedded text scanned for paths/secrets/tokens/hash patterns, generated download filename | Valid, no leakage |
| Security | 10 unauthenticated endpoint probes, wrong-secret/expired/`none`/malformed JWT, unknown-id `404`, traversal probes, malformed DNA profiles, spoofed/oversized/empty/disguised files, response-body leak scan, `frontend/dist` string scan | All rejected as designed |
| Database | Read-only row counts before and after the QA battery; evidence tables compared row-for-row | No case/document/extraction/comparison/decision row created or altered by the QA battery (its probe document and its own `404`/traversal requests were the only touches, and the probe file was deleted again) |
| Responsive | 375/414/640/768/1024/1440 px on login, Command Center, workspace, case list, case detail, report and report library: document-level horizontal overflow, scroll containers, tap targets, mobile menu open/close | 0 px overflow everywhere |
| UI walkthrough | Full demo performed in a browser: sign-in → CNIC → case → upload → analyze → compare → decision → audit → report → PDF → sign-out → protected-route redirect | Completed; 0 console errors/warnings, 0 failed requests |
| Qwen | Configuration surface (`AI_PROVIDER`, `QWEN_API_KEY`, `QWEN_MODEL`, `QWEN_BASE_URL`, `QWEN_TIMEOUT_SECONDS`), factory behaviour and provider tests | Static + test verified; **live Qwen PENDING** (no key) |

Known, non-defect observations recorded during the pass: the Command Center counts
decision outcomes by reading `GET /verifications/{id}/decision` per assessable case
because no aggregate endpoint exists, and the React StrictMode double-invoke in
development duplicates each request — neither occurs in the production build. A
leftover QA draft case (`GV-2026-000021`) carries a `REPORT_GENERATED` audit event
despite having no decision: the report contract marks every missing section
explicitly unavailable and `backend/tests/test_report_audit.py` asserts that nothing is
fabricated for it, so this is intended behaviour rather than a defect.

Two labelled synthetic upload fixtures support the live walkthrough: a document whose
extraction is complete (`EXACT_MATCH` → `VERIFIED`) and one carrying the mock
provider's `GV-PARTIAL` behaviour marker, which loses two markers and therefore lands
on `PARTIAL_MATCH` → `REVIEW_REQUIRED` under rule 3 — a visible demonstration that the
numeric score never decides alone. Both were verified offline against the stored
reference profile (validator acceptance, header, extracted marker count and engine
classification); the engines themselves were not modified.

## 12. Step 13 Verification Record (submission & release readiness)

Step 13 added no component, endpoint, table, rule or dependency. It audited the tree, re-
verified every layer above against the running system, and recorded the evidence in
`.qa-tmp/` (gitignored QA scratch, excluded from any submission).

| Concern | How it was verified in Step 13 | Result |
| --- | --- | --- |
| Submission inventory | `step13_submission_audit.py` classified every file as required source, documentation, example config, generated/runtime, local secret or QA/debug scratch | Reported only: 127 required source files, 40 still untracked, 12 QA items staged — nothing deleted, moved or unstaged |
| Secrets | `step13_secret_audit.py` read backend source, tests, frontend source, docs, the git index and the built bundle, printing masked hashes instead of values | PASS — no real credential present; the development JWT placeholder is tracked as a deployment-time action |
| Documentation ↔ code | `step13_doc_review.py` cross-checked endpoints, env vars, panel markers, weights, decision rules, mandated disclaimers and demo case labels against the source and the database | PASS after the defects it found were corrected in the documents (never in the code) |
| Deterministic engines | Existing suite plus live reads of all stored outcomes | 272 tests pass; `EXACT_MATCH`/`PARTIAL_MATCH`/`NO_MATCH` and the 70/20/10 score are unchanged |
| AI layer boundary | Report and extraction payloads inspected live: AI supplies document fields and candidate STR values only, comparison and decision stay in the deterministic engine | Holds; extraction output is labelled `mock-document-intelligence` and validated before use |
| Security | `step13_security_regression.py`: auth, ownership, `404` indistinguishability, JWT tampering, traversal, malformed/disguised/oversized uploads, response leakage | 170 live checks + 24 targeted tests, 0 failures |
| Production bundle | `step13_bundle_scan.py` over `frontend/dist` | 14 prohibited categories clean; `VITE_API_BASE_URL`-else-same-origin `/api/v1` preserved |
| Database | `step13_db_integrity.py` through a `mode=ro` URI, proving the read-only handle rejects writes, plus deletion probes on a throwaway copy | 64 checks, 0 failures; 123/123 identities/profiles, 25 contiguous cases, `integrity_check = ok`, no FK violation, 6 `RESTRICT` + 4 `CASCADE` foreign keys matching the ORM exactly |
| Demo path | `STEP13_DEMO_CHECKLIST.md`, each BEFORE-DEMO row executed by `step13_demo_preflight.py`; D1–D16 walkthrough performed in a browser | 10/10 pre-flight rows, 15/15 walkthrough items |
| Qwen | Configuration surface and factory guards verified offline (production refuses `mock`; `AI_PROVIDER=qwen` with no key returns a safe `503`) | **live Qwen PENDING** — no key, no call, nothing fabricated |
| Cloud / containers | Environment and tooling inspected (`docker` CLI absent, no cloud credentials, no target verified) | Not deployed, not built, not claimed |

**Shutdown and recovery.** The machine shut down unexpectedly during Step 13. Recovery
inspection (git state, file mtimes, database row counts, storage, ports, QA artifacts)
showed that only the two running dev processes were lost. Backend tests, the production
build, the bundle scan and a 15-check read-only live pass (`step13_postrecovery_check.py`)
were re-run and re-passed with identical database fingerprints, then the UI read path was
re-confirmed in a browser. No work was restarted from scratch and nothing was reset or
reseeded.

Carried into the next stage as known non-defects: document validation inspects magic bytes
and size rather than parsing the file, so a `%PDF-` header with a junk body is accepted at
upload and fails later at extraction validation; and the Command Center still derives
decision counts from per-case reads because no aggregate endpoint exists.
