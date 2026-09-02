# GeneVerify AI

Prototype for **biological-sample substitution prevention** through identity-linked DNA/STR
verification. Built as a hackathon project using **synthetic/demo data only**.

> ⚠️ This project never uses real CNIC numbers, real DNA data, real government databases, or
> real personal data. All identity and DNA records are synthetic.

## Product Flow (implemented)

```
Login → Command Center → Enter CNIC → Retrieve synthetic identity → Create case
→ Upload DNA report → AI-assisted extraction → Deterministic STR comparison
→ Consistency checks → Transparent scoring → VERIFIED / REVIEW_REQUIRED / MISMATCH
→ Deterministic explanation → Verification history → Report + PDF download
```

**Positioning:** AI-assisted identity verification using synthetic identity records,
document intelligence, deterministic STR comparison, evidence scoring, and auditable
verification reports. GeneVerify is a prototype and is not a legally valid forensic
identity system.

## Core Principles

- DNA/STR comparison is **deterministic application logic**. An LLM never decides whether
  two profiles match.
- Alibaba Cloud **Qwen** performs **document extraction** (Step 7), isolated behind a
  service interface (replaceable/mockable). It does not compare STR profiles, score
  evidence or decide an outcome — the explanation attached to a decision is generated
  deterministically by the Step 8 engine, and no AI-generated verdict exists anywhere
  in the system.
- Operators can only **look up** a single synthetic identity by CNIC — the identity
  database is never browsable.
- Designed for future deployment to **Alibaba Cloud** without architectural changes.

## Verification Status at a Glance

Every line below is labelled exactly as it stands on the machine this prototype was built
on. Nothing that has not actually been executed is claimed as working.

| Area | Status | How to reproduce / where it is described |
| --- | --- | --- |
| Backend test suite | **PASS** — 277 passed, none skipped or weakened | `cd backend; python -m pytest` (Getting Started → Backend) |
| Frontend production build | **PASS** — `tsc -b` clean, Vite build succeeds, reproducible hashes | `cd frontend; npm run build` (Getting Started → Frontend; Step 11 → Frontend build & API URL) |
| Security & secret audit | **PASS** — no real API key, JWT, password, database credential or private filesystem path in the source, the documentation, the git index or the production bundle | Step 11 → Security considerations; Step 12 → Verification performed in Step 12 |
| DNA report / PDF content | **PASS** — aggregate STR evidence only, never allele-level data, with the prototype and synthetic-data disclaimers | Step 9 → Verification Report & Audit Trail |
| Live Qwen document extraction | **PENDING** — no `QWEN_API_KEY` is configured here and no live Qwen request has ever been made. The demo runs on the deterministic offline mock provider, which reads the STR table printed in the document itself and falls back to the registered profile only when that text is unreadable; the Qwen path is verified only by its interface, factory behaviour and tests | Step 7 → AI Document Intelligence & STR Extraction |
| Alibaba Cloud deployment | **PENDING** — nothing has been deployed. Configuration, guards and the entrypoint are ready and tested; the notes are a plan, not a record | Step 11 → Deploying to Alibaba Cloud (prepared, not executed) |
| Docker image build / run | **PENDING** — `backend/Dockerfile` is authored but has never been built or started, because no Docker engine is installed on this machine | Step 11 → Docker (optional) |

## Repository Layout

```
.
├── Start GeneVerify.bat   one-click local startup (backend + frontend + browser)
├── Stop GeneVerify.bat    stops only this project's two servers
├── backend/    FastAPI + SQLAlchemy + Pydantic backend (SQLite initially)
├── frontend/   React + TypeScript + Vite + Tailwind CSS
└── docs/       Architecture documentation
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design.

## One-Click Local Startup

Double-click:

```
Start GeneVerify.bat
```

The launcher automatically starts the backend and the frontend and opens the
application at <http://localhost:5173>.

To stop the local application:

```
Stop GeneVerify.bat
```

What the launcher does, in order:

| # | Action |
| --- | --- |
| 1 | Resolves its own folder (`%~dp0`), so it works from any current directory and after the project is moved or copied. |
| 2 | Verifies `backend\`, `frontend\`, `backend\.venv\Scripts\python.exe`, `frontend\node_modules` and `npm`, and prints the exact fix for anything missing. |
| 3 | Starts the backend in its own window — `backend\.venv\Scripts\python.exe run.py` with working directory `backend\` — serving uvicorn on **port 8000** (`127.0.0.1` in development, per `backend/run.py`). The project's own virtual environment is used directly; nothing has to be activated first. |
| 4 | Starts the frontend in its own window — `npm run dev` with working directory `frontend\` — Vite on **port 5173** (`frontend/vite.config.ts`). |
| 5 | If a port is already listening it prints `Backend already running.` / `Frontend already running.` and does **not** start a second copy. That is what prevents the old duplicate-server case where a second Vite silently moved to 5174. |
| 6 | Polls `http://127.0.0.1:8000/api/v1/health` until it answers `200` (one request per second, ~90 s budget), then `http://localhost:5173` the same way. No blind `sleep` — the browser is never opened against a service that is not up yet. |
| 7 | Opens <http://localhost:5173> in the default browser. The backend health endpoint is never used as the landing page. |

When a service does not come up, the launcher names it and says to check the
matching window (`GeneVerify Backend` / `GeneVerify Frontend`). Those windows are
`cmd /k` windows, so a crash leaves the traceback on screen instead of closing.

Open the app as `http://localhost:5173`, not `http://127.0.0.1:5173`: the backend
CORS allow-list (`CORS_ORIGINS` in `backend/.env`) contains exactly
`http://localhost:5173`.

`Stop GeneVerify.bat` walks the process chain behind ports 8000 and 5173 and stops
only the processes whose command line belongs to this project (the uvicorn
interpreter and its children, the `npm`/`vite`/`esbuild` chain, and the two
dedicated console windows). A port held by an unrelated program is reported and
left running — no `taskkill /IM python.exe`, no killing every `node`. It deletes
no files, changes no data, seeds nothing and runs no git command; `backend/geneverify.db`
and `backend/storage/` are untouched.

The one-click path assumes the two one-time setup steps already happened (create
`backend\.venv` and run `npm install`) — see [Getting Started](#getting-started).

## Getting Started

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # runtime only
pip install -r requirements-dev.txt      # + pytest/httpx, needed to run the tests
copy .env.example .env          # then adjust as needed
uvicorn app.main:app --reload   # http://localhost:8000 (docs at /docs)
```

Health endpoint: `GET http://localhost:8000/api/v1/health`

Seed the synthetic demo dataset (safe to rerun — existing CNICs are skipped):

```powershell
cd backend
python -m app.database.seed
```

Seed the demo operator account (idempotent — safe to rerun; the password is read
from `DEMO_ADMIN_PASSWORD` in `.env` and stored only as an Argon2 hash):

```powershell
cd backend
python -m app.database.seed_users
```

CNIC identity lookup (single record only, never the whole database) —
**requires a bearer token**:
`GET http://localhost:8000/api/v1/identity/{cnic}`

Run tests:

```powershell
cd backend
pytest
```

### Frontend

```powershell
cd frontend
npm install
copy .env.example .env.local    # then adjust as needed
npm run dev                     # http://localhost:5173
```

Production build:

```powershell
cd frontend
npm run build
```

## Synthetic Demo Dataset

**All identity and DNA records in this prototype are synthetic demonstration data.**

- 123 records total: 120 deterministically generated + 3 hand-crafted demo records.
- Every value (names, addresses, dates, CNICs, STR profiles) is fictional and derived
  from a fixed RNG seed (`20260828`), so every environment reproduces the same dataset.
- CNICs use the never-issued `99900` demo prefix in Pakistan-style `NNNNN-NNNNNN-N`
  format. They do not reference real people or registries.
- Each identity has exactly one reference STR profile: 20 markers
  (D3S1358, vWA, FGA, D8S1179, D21S11, D18S51, D5S818, D13S317, D7S820, CSF1PO,
  TH01, TPOX, D16S539, D2S1338, D19S433, D12S391, D10S1248, D1S1656, D22S1045,
  SE33), each with two synthetic allele values.
- Operators can only look up a single record by exact CNIC. **There is no endpoint to
  browse, list, or export the identity database.**

### SYNTHETIC DEMO IDENTIFIERS ONLY

These CNICs exist only in the seeded demo database and are safe for the presentation:

| Demo CNIC | Purpose | Status |
| --- | --- | --- |
| `99900-0000001-1` | Known identity with known reference profile (match case) | active |
| `99900-0000002-3` | Different reference profile (mismatch case) | active |
| `99900-0000003-5` | Record reserved for manual-review testing | under_review |

## Authentication (Step 3)

Operators must sign in before using the application. Login issues a short-lived
JWT; the identity lookup endpoint rejects unauthenticated requests with `401`.

- Passwords are hashed with **Argon2id** (`argon2-cffi`); plaintext is never stored or logged.
- JWTs are signed with `JWT_SECRET_KEY` from the environment (`HS256`, configurable
  expiry). The repo only ships an insecure development placeholder — production
  **must** use a strong secret (the app refuses to boot in production without one).
- Protected endpoints use the reusable `get_current_user` / `require_role(...)`
  FastAPI dependencies, so all future verification/document/report routes inherit
  the same protection.

| Endpoint | Description |
| --- | --- |
| `POST /api/v1/auth/login` | Exchange username/password for a bearer token |
| `GET /api/v1/auth/me` | Current authenticated user (safe fields only) |
| `POST /api/v1/auth/logout` | Logout (stateless JWT: client discards the token) |

### SYNTHETIC DEMO CREDENTIALS ONLY

Created by `python -m app.database.seed_users` (password supplied via the
`DEMO_ADMIN_PASSWORD` environment variable, never hardcoded in source):

| Username | Password | Role |
| --- | --- | --- |
| `admin` | `GeneVerify@2026` | admin |

> These are hackathon demo credentials and **MUST be replaced before any
> production deployment**.

### Frontend authentication flow

Unauthenticated visitor → `/login` page → token stored via the isolated
`tokenStorage` module → protected app shell, landing on the Command Center (`/`) →
header shows the signed-in user with a logout action. Any `401` from the API clears
the session and returns to login.

**Prototype limitation:** the token is kept in `localStorage` for simplicity;
this is XSS-vulnerable and is planned to be upgraded to HttpOnly cookie
sessions before deployment (all token handling is isolated in
`services/tokenStorage.ts` + `services/apiClient.ts`).

## Verification Cases (Step 4)

The case-management foundation for the verification workflow. A case links one
synthetic identity to one operator-created verification and carries the document,
extraction, STR comparison, scoring and final result recorded by the later steps —
all of which exist today.

| Endpoint | Description |
| --- | --- |
| `POST /api/v1/verifications` | Create a `draft` case for a CNIC (identity must exist) |
| `GET /api/v1/verifications` | Cases accessible to the current user |
| `GET /api/v1/verifications/{verification_id}` | One accessible case |

- **Verification ID:** human-readable, report-safe `GV-YYYY-NNNNNN` generated
  server-side (unique, collision-retried). Internal database IDs are never the
  public identifier and IDs are never derived from the CNIC.
- **Statuses:** `draft` (default) · `in_progress` · `completed` ·
  `review_required` · `cancelled`. No state-machine logic yet.
- **Ownership:** the creator always comes from the authenticated JWT, never
  from request data. Officers see only their own cases; admins can review all
  cases; another user's case answers `404` so existence is never disclosed.
- **No DNA exposure:** case responses contain a bounded identity summary only
  — never the STR profile, password data or database internals. The identity
  table remains non-browsable (no bulk endpoints added).
- **Frontend:** `/verify` (workspace: CNIC → confirm identity → create case) and
  `/verifications` (+ case detail view with DNA analysis), both protected by login.

## Deterministic STR DNA Matching Engine (Step 5)

The core scientific component: a pure Python engine that compares a submitted
STR profile against the case's reference profile marker by marker.

| Endpoint | Description |
| --- | --- |
| `POST /api/v1/verifications/{verification_id}/dna/compare` | Compare a submitted STR profile against the case's reference DNA |

- **Deterministic by construction:** same two profiles always produce the same
  result. No randomness, no network, no AI — the engine works fully offline.
- **AI is NOT used for DNA matching.** An LLM/Qwen never decides whether two
  profiles match. Qwen's one live role is document extraction (Step 7), behind a
  replaceable service interface; the decision explanation is deterministic.
- **Canonical panel reused:** the existing 20-marker panel and allele-range
  rules in `app/services/str_engine/panel.py` are the single source of truth.
- **Allele order never matters:** `[15, 16]` vs `[16, 15]` is a `MATCH`.
- **Missing data is explicit:** an absent submitted marker is
  `MISSING_SUBMITTED`, never a `MISMATCH` (and vice versa for the reference).
- **Marker statuses:** `MATCH` · `MISMATCH` · `MISSING_REFERENCE` ·
  `MISSING_SUBMITTED` · `INVALID`.
- **Overall classification:** `EXACT_MATCH` (all 20 markers match) ·
  `PARTIAL_MATCH` (some but not all — **never** an identity confirmation) ·
  `NO_MATCH` (zero matches) · `INVALID` (not evaluable). The
  `match_percentage` is a marker count ratio — not a forensic probability.
- **Strict validation:** empty profiles, unexpected/malformed markers, wrong
  allele counts, non-numeric/null alleles and out-of-range values are rejected
  with structured 422 errors — invalid data is never silently repaired.
- **Security boundary:** the client supplies only `submitted_profile`.
  `reference_profile` in the request is rejected (`extra="forbid"`); the
  reference is always resolved server-side: case → identity → dna_profile.
  Step 4 ownership rules apply; there is no bulk DNA endpoint and the identity
  lookup still exposes no DNA.
- **Persistence:** every run is stored in `dna_comparison_results` (aggregate
  counts + marker breakdown + submitted evidence for the prototype audit
  trail; reference DNA is not duplicated). A successful comparison moves a
  `draft` case to `in_progress`.
- **Frontend:** the case detail page gained a DNA Analysis section with
  structured STR profile input, a `[Compare DNA]` action, the overall result,
  match percentage, marker summary and a per-marker table.

> This prototype STR comparison engine performs deterministic profile comparison
> against synthetic demonstration data. It is not a forensic probability
> calculator and does not constitute legally valid identity confirmation.

## Secure Document Upload (Step 6)

The document foundation for the final workflow: authenticated operators can
attach DNA/blood-test documents (PDF, PNG, JPG, JPEG) to an existing
verification case. **Step 6 does NOT perform AI extraction** — documents wait
in `UPLOADED` status until Step 7 processes them with Qwen/OCR into structured
STR data for the deterministic comparison engine.

| Endpoint | Description |
| --- | --- |
| `POST /api/v1/verifications/{verification_id}/documents` | Multipart upload to an accessible case (201) |
| `GET /api/v1/verifications/{verification_id}/documents` | Metadata list of a case's documents |
| `GET /api/v1/verifications/{verification_id}/documents/{document_id}/file` | Secure download of a stored document |
| `DELETE /api/v1/verifications/{verification_id}/documents/{document_id}` | Remove a document and its stored file |

- **Model:** `verification_documents` stores metadata only (document id,
  original filename, server-generated stored filename, content type, size,
  type, status, uploader, timestamps). File binaries are never stored in
  SQLite — they live on the local filesystem under `DOCUMENT_STORAGE_PATH`
  (default `backend/storage/documents`, gitignored, never served statically).
- **Document ID:** report-safe `GVD-YYYY-NNNNNN`, generated server-side,
  unique, never derived from the CNIC or the original filename. Internal
  database ids are never exposed.
- **Types & statuses:** `DNA_REPORT` (upload default) · `BLOOD_TEST` ·
  `OTHER`; processing statuses `UPLOADED` · `PROCESSING` · `PROCESSED` ·
  `FAILED` — Step 6 only ever writes `UPLOADED`.
- **Validation:** extension, declared MIME type, size (configurable
  `MAX_DOCUMENT_SIZE_MB`, default 10 MB → HTTP 413) and magic-byte signatures,
  so a renamed `.pdf` that is not really a PDF is rejected with 422.
- **Secure storage:** stored filenames are server-generated uuid hex names;
  user-supplied filenames are display metadata only. Every resolved path must
  stay inside the storage root — traversal attempts (`../../…`) are rejected.
  There are no public upload/download URLs and no static mount of storage.
- **Ownership:** uploads require an existing, accessible case. The uploader is
  always the authenticated user (identity/case/user ids from the request are
  never accepted); officers access only their own cases' documents, admins all;
  foreign cases/documents answer `404`.
- **Response hygiene:** document metadata responses contain no storage paths,
  no stored filenames, no DNA content and no credentials.
- **Frontend:** the case detail page gained a drag-and-drop **DNA Document**
  section (client-side type/size checks, upload states, success/error
  messaging, document list with secure View/Delete) — kept visually distinct
  from the Manual/Test STR Profile section from Step 5.

## AI Document Intelligence & STR Extraction (Step 7)

Uploaded documents can now be analyzed by AI document intelligence. The AI
performs **document understanding and extraction only**: it reads the report
and returns structured fields. **DNA comparison is performed by a
deterministic STR engine** — the AI is never asked whether a profile
matches, and it never produces an identity verdict.

| Endpoint | Description |
| --- | --- |
| `POST /api/v1/verifications/{verification_id}/documents/{document_id}/process` | Run the AI extraction pipeline on an accessible document |
| `GET /api/v1/verifications/{verification_id}/documents/{document_id}/extraction` | Safe extraction result (AI data, clearly labelled) |

- **AI service abstraction:** `app/services/ai/` holds every AI concern —
  the `DocumentIntelligenceService` ABC, `QwenDocumentIntelligenceService`
  (Alibaba Cloud Qwen via its OpenAI-compatible chat endpoint) and
  `MockDocumentIntelligenceService` (deterministic, network-free). Routes
  depend on the interface only; the STR engine, models and frontend contain
  zero Qwen code.
- **Provider configuration:** `AI_PROVIDER=qwen|mock` plus `QWEN_API_KEY`,
  `QWEN_MODEL`, `QWEN_BASE_URL`, `QWEN_TIMEOUT_SECONDS` from the environment
  (see `backend/.env.example`). No keys are hardcoded; the app always boots;
  an unconfigured provider answers `503 "AI provider is not configured."`
  Production refuses to silently use the mock.
- **Pipeline:** auth/ownership → metadata → file-on-disk check →
  `PROCESSING` → provider extraction → strict Pydantic validation →
  persisted `document_extractions` row → `PROCESSED` (or `FAILED` with a
  safe audit note). Already-processed documents are not re-analyzed (409).
- **Strict extraction schema:** unknown markers, non-numeric/null alleles,
  wrong allele counts, out-of-range values and arbitrary extra fields are
  rejected — malformed AI output is never silently repaired. Canonical
  markers/ranges come from the existing `str_engine/panel.py` only.
- **Consistency checks:** extracted CNIC/name are compared to the case's
  identity with simple deterministic equality (`CONSISTENT` /
  `INCONSISTENT` / `NOT_DETECTED`) and labelled *document identity-field
  consistency* — never identity verification.
- **Step 5 seam:** the extracted profile feeds the existing
  `POST .../dna/compare` endpoint unchanged (no duplicated engine); the
  manual/test comparison endpoint keeps working.
- **Cost control:** AI runs only on an explicit "Analyze with AI" click —
  never on page load — and stored extractions are served without new calls.
- **Security:** no API keys, raw provider responses, storage paths or stack
  traces leave the backend; the extraction prompt treats document content
  as untrusted data (prompt-injection resistant); the reference profile is
  never part of extraction responses.
- **Frontend:** the document list gained **Analyze with AI**, processing
  states, and an **AI EXTRACTION** panel (patient name, CNIC, report date,
  consistency badges, `20 / 20` marker count, Marker/Allele 1/Allele 2
  table) labelled "AI-extracted data — requires deterministic validation",
  plus **[Compare With Registered DNA]** which invokes the deterministic
  engine and renders the standard comparison result.

> GeneVerify is a hackathon prototype using synthetic demonstration data and
> is not a legally valid forensic identity system.

## Verification Decision Engine & Evidence Scoring (Step 8)

Combines existing evidence from Steps 5 and 7 into a transparent
verification assessment. The decision engine is entirely deterministic —
**no LLM/AI is used to decide whether DNA matches or to produce a verdict.**

| Endpoint | Description |
| --- | --- |
| `POST /api/v1/verifications/{verification_id}/decision` | Calculate and persist the verification decision |
| `GET /api/v1/verifications/{verification_id}/decision` | Retrieve the current decision |

- **Prototype Evidence Score** (transparent weighting, total 100):
  DNA STR comparison: 70 · Identity consistency: 20 · Document consistency: 10
- **Decision rules** (classification-driven; the score never determines the
  outcome alone):
  1. EXACT_MATCH + consistent evidence → `VERIFIED`
  2. EXACT_MATCH + inconsistency detected → `REVIEW_REQUIRED`
  3. PARTIAL_MATCH → `REVIEW_REQUIRED` (partial is never VERIFIED)
  4. NO_MATCH → `MISMATCH`
  5. INVALID → `REVIEW_REQUIRED`
  6. Missing DNA evidence → `REVIEW_REQUIRED` (or 409 if no comparison exists)
- **Explanation generation:** deterministic, built from actual evidence. Never
  invents facts.
- **Case status update:** `VERIFIED` → completed · `MISMATCH` → completed ·
  `REVIEW_REQUIRED` → review_required. The decision engine controls the status
  update; clients never manipulate it directly.
- **Security:** responses expose only safe summary fields — never raw DNA
  profiles, reference alleles, passwords, API keys, filesystem paths or
  provider internals.
- **Frontend:** the case detail page gained a **Verification Assessment**
  section with a `[Run Verification Assessment]` button and a result card
  showing the decision, score, evidence breakdown and system explanation.

> The evidence score is a deterministic prototype scoring mechanism and is
> not a forensic probability or legally valid identity determination.

## Verification Report & Audit Trail (Step 9)

Every completed action on a case is recorded in an append-only audit trail, and
the accumulated evidence is projected into a structured verification report with
a server-rendered PDF. **The report introduces no new evidence, no new scoring
and no new AI involvement** — it reads Steps 4–8 results and presents them.

| Endpoint | Description |
| --- | --- |
| `GET /api/v1/verifications/{verification_id}/report` | Structured report (JSON) — read-only, records no audit event |
| `GET /api/v1/verifications/{verification_id}/report/download` | Same report as a professional PDF; records `REPORT_GENERATED` |

- **Audit trail** (`verification_audit_events`): one row per successful action —
  `CASE_CREATED`, `DOCUMENT_UPLOADED`, `DOCUMENT_PROCESSED`, `DNA_COMPARED`,
  `DECISION_GENERATED`, `REPORT_GENERATED`. Each row stores the case, the
  authenticated actor, the event type, a short human-readable summary and the
  timestamp. Written exclusively by the service layer, never from client input.
- **Reads never write events:** viewing a case, listing events or opening the
  report page leaves the timeline untouched, so the audit trail reflects real
  operations, not page refreshes. Failed operations record no success event.
- **Event safety:** audit descriptions carry identifiers and aggregate results
  only — never passwords, JWTs, API keys, raw STR markers, document contents,
  filesystem paths or raw AI responses.
- **No backfill (known limitation):** events are written as actions happen, so a
  case created before Step 9 has an empty trail until its next action. Its report
  then states "No audit events recorded." instead of reconstructing history — the
  timeline is a genuine record, never an inferred one.
- **Report structure** (nine parts): report header · identity information ·
  document information · AI extraction (always labelled *AI-extracted
  information — validated before use.*) · DNA/STR analysis (classification,
  match percentage and marker counts only, with the statement "DNA comparison
  was performed using the deterministic STR matching engine.") · evidence
  assessment (DNA 70 / identity 20 / document 10, total 100) · final decision
  with the engine's deterministic explanation · audit timeline · disclaimer.
- **Incomplete evidence is stated, never invented:** "No document submitted.",
  "Document has not been processed.", "DNA comparison not available.",
  "Verification decision not available."
- **PDF generation:** rendered server-side with `fpdf2` (no headless browser,
  no JavaScript) — A4, brand header/footer, numbered sections, page numbers,
  "Prototype report — not a forensic identification system" footer, and a
  `GeneVerify-Report-<VERIFICATION ID>.pdf` download name.
- **Access control:** both endpoints reuse the Step 4 ownership rules —
  officers see their own cases, admins see all, foreign cases answer `404` so
  existence is not disclosed; unauthenticated requests answer `401`.
- **Frontend:** a **Verification Report** summary card on the case detail page
  (Verification ID, decision, evidence score, DNA match, identity/document
  consistency, audit-trail count) with **[ View Full Report ]** and
  **[ Download PDF Report ]** (Step 10), plus the protected report page
  `/verifications/{verification_id}/report` (nine sections, print-friendly) and
  a reusable `AuditTimeline` component.

> Reports are prototype evidence summaries built from synthetic demonstration
> data. They are not forensic reports and carry no legal standing.

## Command Center & UI Polish (Step 10)

Frontend-only step: the existing workflow is now presented through one consistent
shell. No backend behaviour, endpoint, scoring formula, decision rule, provider,
audit or report architecture changed, and the 123 synthetic identities / 123 DNA
profiles are untouched.

### Navigation and routes

| Route | Screen | Purpose |
| --- | --- | --- |
| `/login` | `LoginPage` | The only public surface |
| `/` | `DashboardPage` | Command Center — signed-in entry point |
| `/verify` | `VerificationWorkspacePage` | CNIC entry → identity confirmation → create case |
| `/verifications` | `VerificationCasesPage` | Case history |
| `/verifications/{id}` | `VerificationCaseDetailPage` | Case header → pipeline → evidence → audit trail → report |
| `/verifications/{id}/report` | `VerificationReportPage` | Full report + **Download PDF Report** |
| `/reports` | `ReportsPage` | Report library over the existing case/decision data |
| `/lookup` | `IdentityLookupPage` | Original single-record lookup, kept for continuity |
| `/overview` | `HomePage` | Project positioning + backend health |

`AppLayout` carries **Dashboard · Verify Identity · My Cases · Reports**, the
signed-in user's name and role, and the logout control. Below 640 px the same links
move behind a keyboard-accessible hamburger (`aria-expanded` + `aria-controls`,
Escape closes it and returns focus, navigating closes it, logout stays reachable).

### Command Center honesty

The four overview cards (Verification Cases, Pending Review, Verified, Mismatch) use
real records only. The backend exposes no aggregate statistics endpoint, and the Step 8
engine maps both VERIFIED and MISMATCH to a `completed` case, so
`hooks/useCaseOverview.ts` takes status counts straight from `GET /verifications` and
then performs **bounded** `GET /verifications/{id}/decision` reads (the 40 most recent
cases that can hold a decision) so outcomes come from stored decisions. A case whose
decision was never read is labelled *Not checked* rather than *No decision yet*, and
the dashboard prints its own counting basis. Nothing is estimated or invented.

### Case detail, pipeline and report

- The eight-stage **Verification Pipeline** is pure presentation: every stage state is
  derived from the existing report payload's per-stage `available` / `message` fields,
  so no business rule is duplicated in React.
- `hooks/useVerificationReport.ts` is the single owner of `GET .../report` for a case,
  feeding pipeline, audit timeline and report preview from one request;
  `VerificationReportSection` is now presentational. Downloading still calls the
  existing Step 9 endpoint and then silently re-reads the report, which is what makes
  the fresh `REPORT_GENERATED` event appear in the timeline.
- The result card shows the stored decision, the stored evidence score out of 100, the
  DNA / identity / document components and the backend's own explanation, plus the
  existing prototype disclaimer. No score is recalculated in the browser.
- Standardized states live in `components/StateBlocks.tsx`: `Skeleton`,
  `LoadingBlock`, `EmptyState`, `ErrorState` (callers pass a precise title, so a
  failed request is named rather than generic) and `InfoNotice` for expected
  outcomes such as an unknown or incomplete CNIC — those no longer read as
  "Something went wrong". `SectionCard`, `Field` and `ScrollHint` round out the set;
  `ScrollHint` marks the tables that scroll sideways on narrow screens. No UI text can
  surface a stack trace, database error, file path, API key, JWT, password hash or raw
  provider response.
- The API stores naive UTC timestamps, so `utils/format.ts` parses them as UTC before
  rendering, keeping absolute and relative times consistent.

### Visual and accessibility layer

`index.css` holds the design primitives: brand colour tokens, `.gv-card`,
`.gv-glass`, `.gv-badge`, the `.gv-btn` variants, staggered entrance helpers,
`.gv-skeleton` and six keyframe tokens (`gv-fade-up`, `gv-fade-in`, `gv-pop`,
`gv-menu`, `gv-shimmer`, `gv-ping`), all neutralised under
`@media (prefers-reduced-motion: reduce)`. No animation or UI library was added; the
icons in `components/Icons.tsx` are hand-written inline SVG.
`CaseStatusBadge` / `DecisionBadge` keep the backend enum values verbatim and add an
icon plus text so status never depends on colour alone. Inputs are labelled, focus is
visible, headings are hierarchical, loading regions announce themselves via
`aria-live`, and decorative glyphs are `aria-hidden`.

### Verification performed

- Backend suite unchanged and green: **244 passed**. `npm run build` clean.
- Browser QA of the full flow at 375 / 414 / 640 / 1024 / 1440 px: no horizontal
  overflow, no clipped card, no broken table, no hidden control.
- Unauthenticated `401`, forged-token `401` and bad-password `401` re-checked; API
  responses and the built bundle scanned for leaked internals — clean.
- Known limitation: reading a case that has no decision answers `404` by design, so
  the dashboard and report library log those browser responses while counting.

## Deployment & Production Readiness (Step 11)

Step 11 changed **configuration, startup and build wiring only**. The STR engine,
20-marker panel, scoring formula, decision rules, Qwen extraction schema, auth
architecture, ownership rules, document validation rules and report semantics are
untouched, and every Step 1–10 test still passes unchanged.

### Target architecture (unchanged, deliberately simple)

```
Browser
   ↓
Frontend (static build: frontend/dist)
   ↓ HTTPS in production; same-origin behind a reverse proxy, or CORS_ORIGINS
FastAPI backend (app.main:app, uvicorn)
   ↓
SQLite (DATABASE_URL)          ·  Document storage (DOCUMENT_STORAGE_PATH)
FastAPI backend
   ↓ HTTPS, backend-only, API key from the environment
Alibaba Cloud Qwen (OpenAI-compatible endpoint)
```

No Kubernetes, no microservices, no Redis, no Celery, no object storage, no extra
cloud services. One process, one database file, one directory.

### Backend startup

The real ASGI target is `app.main:app` (module-level `app = create_app()`), run
with `backend/` as the working directory so `.env` and the relative SQLite/storage
paths resolve:

```powershell
cd backend
python run.py                      # reads HOST + PORT from the environment
```

or directly:

```powershell
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`run.py` is the deployment-friendly entrypoint: `PORT` (as injected by most PaaS
platforms) is honoured and validated (`1–65535`), and `HOST` defaults to
`127.0.0.1` in development but `0.0.0.0` in production unless set explicitly.

Health check: `GET /api/v1/health` → `{"status":"ok","app":...,"environment":...,
"version":...}` — no credentials, no environment dump, no internal paths, no
provider configuration.

### Production environment variables

Real environment variables win over `.env` (pydantic-settings). Every name below is
read from the environment by the backend — `app/core/config.py`, except `HOST`/`PORT`
which `run.py` reads directly; the full annotated list lives in
`backend/.env.example`.

| Variable | Default (dev) | Production note |
| --- | --- | --- |
| `APP_NAME` / `APP_VERSION` | GeneVerify AI API / 0.1.0 | reported by `/health` |
| `APP_ENV` | `development` | `development` \| `staging` \| `production` (validated) |
| `DEBUG` | `false` in code (`true` in the local `.env`) | **production refuses `true`** |
| `API_PREFIX` | `/api/v1` | also the frontend's default base path |
| `DATABASE_URL` | `sqlite:///./geneverify.db` | writable mounted path; any SQLAlchemy URL works |
| `CORS_ORIGINS` | `http://localhost:5173` | exact public frontend origin(s), comma-separated |
| `LOG_LEVEL` | `INFO` | validated against standard levels |
| `JWT_SECRET_KEY` | insecure placeholder | **production refuses the placeholder**; ≥ 16 chars, `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_ALGORITHM` | `HS256` | HMAC only (HS256/384/512) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | 1–1440 |
| `DEMO_ADMIN_USERNAME` / `DEMO_ADMIN_PASSWORD` | `admin` / unset | seed-time only, replaced before any real deployment |
| `DOCUMENT_STORAGE_PATH` | `storage/documents` | writable mounted directory |
| `MAX_DOCUMENT_SIZE_MB` | `10` | 1–100 |
| `AI_PROVIDER` | `mock` | `qwen` in production (mock is refused there) |
| `QWEN_API_KEY` | unset | backend-only secret; never in `VITE_*` |
| `QWEN_MODEL` / `QWEN_BASE_URL` / `QWEN_TIMEOUT_SECONDS` | `qwen-vl-max` / DashScope intl / `60` | switch base URL for CN-region accounts |
| `HOST` / `PORT` | unset | read by `run.py` only |

There is intentionally **no** report configuration: PDFs are rendered in-process by
`fpdf2` from the existing report payload.

### Production startup checks

`create_app()` runs `_production_startup_checks()` and refuses to boot in
`APP_ENV=production` when `JWT_SECRET_KEY` is still the insecure placeholder or
`DEBUG` is enabled (a `RuntimeError` naming the setting, never its value). It logs
warnings when `CORS_ORIGINS` still lists a development loopback origin or when
`AI_PROVIDER=mock` is configured for production. Outside production the existing
behaviour is unchanged — development keeps its defaults and warnings.

### Frontend build & API URL

```powershell
cd frontend
npm run build        # tsc -b && vite build  →  frontend/dist
```

The API base URL comes from `VITE_API_BASE_URL` at build time:

- **Development** (`npm run dev`): unset is fine — the dev build falls back to
  `http://localhost:8000/api/v1`.
- **Production build with the variable set**: that exact URL is used.
- **Production build without it**: the bundle falls back to **same-origin
  `/api/v1`**, which is what a single-host reverse-proxy deployment needs.
  `http://localhost:8000` is *not* hardcoded into production output — the built
  bundle was scanned to confirm this.

`VITE_*` values are compiled into the browser bundle and publicly readable, so only
a URL may ever be placed there. Serve `frontend/dist/` with SPA history fallback
(verified: a deep link to `/login` returns the app).

### Database persistence

SQLite stays the hackathon database — no migration, no auto-PostgreSQL switch.
Startup performs a **non-destructive** `Base.metadata.create_all` (it only ever
creates missing tables; it never drops or recreates), the parent directory of a
file-based SQLite path is created if missing (so a mounted empty `/data` works), and
`PRAGMA foreign_keys=ON` is enforced per connection. Seed commands remain
idempotent. Deployment must not delete `geneverify.db` or the `data/` volume.

### Document storage

`DOCUMENT_STORAGE_PATH` is a configurable, gitignored, non-static directory
(`storage/` in `.gitignore`), created on demand and outside `frontend/`. Uploads keep
server-generated filenames (uuid4 + extension), path-traversal protection,
ownership checks, extension + declared-MIME + magic-byte validation and the size
limit. Serving a file happens only through the authenticated download endpoint.

### Docker (optional)

`backend/Dockerfile` and `backend/.dockerignore` exist as a convenience for
container-based hosting: `python:3.14-slim` (matching the verified local
interpreter), runtime dependencies only, non-root user, `EXPOSE 8000`, a mounted
`/srv/geneverify/data` directory for the database and documents, all configuration
through environment variables, no secrets in the image, and a health check against
`/api/v1/health`. **It was authored but not built or run here — no Docker engine is
installed on this machine**, so container behaviour is unverified. A plain
`uvicorn`/`python run.py` deployment on one host is equally supported and needs
nothing new.

### Python dependencies

`backend/requirements.txt` now holds **runtime** dependencies only; test tooling
moved to `backend/requirements-dev.txt` (`-r requirements.txt`, `pytest`, `httpx`).
This fixed a real deployment bug: the previous manifest listed `httpx2`, a different
PyPI package whose installed module is `httpx2` (confirmed from its `RECORD`), so it
never provided the `httpx` module that `fastapi.testclient` requires. `httpx` was
present in this virtualenv only because it had been installed manually, so a clean
`pip install -r requirements.txt` would not have been able to run the test suite.

### Deploying to Alibaba Cloud (prepared, not executed)

Nothing in the code is ECS/ACK/function-specific, so the simplest path is one small
ECS instance (or any PaaS web service): put the backend behind its own process, serve
`frontend/dist` from nginx (or let the backend host it), terminate TLS there, set the
environment variables above with a real `JWT_SECRET_KEY` and
`AI_PROVIDER=qwen` + `QWEN_API_KEY`, and mount a persistent disk for the SQLite file
and `DOCUMENT_STORAGE_PATH`. **No cloud deployment was performed or verified in this
step** — no credentials, no network calls to Alibaba Cloud and no live Qwen request
were made; the Qwen wiring was validated statically and by the offline provider
tests only.

### Hackathon demo workflow (what to click)

1. Start the backend (`python run.py`) and `npm run dev` (or serve `dist`).
2. Sign in as `admin` / `GeneVerify@2026` → Command Center.
3. **Verify** → enter a synthetic CNIC such as `99900-0000001-1` → confirm the
   identity → create the case.
4. Open the case → **Upload document** (PDF/PNG/JPG ≤ 10 MB) → **Analyze with AI**
   (mock provider locally, Qwen when configured).
5. Review the AI extraction → **Compare With Registered DNA** (deterministic STR).
6. Generate the decision → open the report → **Download PDF Report**.
7. Check the **Reports** library and the audit timeline; **Log out** → protected
   routes return to `/login`.

### Security considerations

- Secrets are environment-only. Neither `SECRET_KEY` nor any JWT, password hash,
  filesystem path, database credential or Qwen key appears in API responses, in
  `frontend/dist` or in the git index (`.env` files are ignored; only
  `.env.example` placeholders are tracked).
- Every protected endpoint requires a valid bearer token; ownership failures answer
  `404` so case existence is never disclosed; CORS is an explicit origin allowlist
  (verified: a configured origin is accepted, an unconfigured one is rejected).
- Error responses are uniform (`HTTPException` detail, `422` validation summary,
  `500 "Internal server error"`) — no stack traces or database internals.
- Malformed AI output and spoofed file content are rejected rather than repaired.

> **Synthetic-data disclaimer.** GeneVerify is a hackathon prototype built entirely
> on synthetic demonstration data. The identity database is **not** a real national
> identity registry, the DNA profiles are **synthetic** values generated from a fixed
> RNG seed, and nothing here is a legally or forensically valid identity
> verification system. There is **no** connection to, or implication of access to,
> any real government database.

### Verification performed in Step 11

- Backend suite: **272 passed** (244 previous + 28 new
  `backend/tests/test_deployment_readiness.py`), no regressions.
- `npm run build` clean; production bundle scanned — no `localhost:8000`, no
  `sk-`-style key, no `QWEN`/`JWT`/`SECRET`/`DATABASE_URL` string, no password hash.
- Live 37-check HTTP run against a server started with `python run.py`: the full
  15-step workflow plus the security battery, all passing; one scratch case
  (`GV-2026-000023`) and its document/report were created for it.
- Production bundle verified in a browser via `vite preview` against a second
  backend instance on a `PORT`-supplied port with an extended `CORS_ORIGINS`:
  login, dashboard, report page, PDF download (audit event written), logout and the
  protected-route redirect all worked with zero CORS errors.
- Row counts after all of the above: 123 identity records and 123 DNA profiles
  unchanged.

## Final Integration, QA & Demo Readiness (Step 12)

Step 12 added no feature, endpoint, table, scoring rule or engine change, and no new
test — verification found no defect in the deterministic layers, so there was nothing
to fix there. What it did was exercise the assembled pipeline from both sides (live
HTTP and a real browser session), polish the presentation layer where the walkthrough
showed genuine weaknesses, and record the demo scenarios below. `docs/ARCHITECTURE.md`
§11 carries the matching verification record.

### Demo scenarios (already stored — nothing to prepare)

All four cases belong to the same synthetic identity, `Sami Demoosh`, CNIC
`99900-0000001-1`, so a single CNIC entry can reach every outcome:

| Demo | Case | STR result | Evidence score | Decision |
| --- | --- | --- | --- | --- |
| A — clean verification | `GV-2026-000024` | `EXACT_MATCH` 20/20 | 100 | **VERIFIED** |
| A — alternative (2 documents) | `GV-2026-000023` | `EXACT_MATCH` 20/20 | 100 | **VERIFIED** |
| B — human review | `GV-2026-000019` | `PARTIAL_MATCH` 15/20 (75 %) | 52 | **REVIEW_REQUIRED** |
| C — mismatch | `GV-2026-000020` | `NO_MATCH` 0/20 | 0 | **MISMATCH** |

`GV-2026-000024` is the case created by the Step 12 browser walkthrough end to end
(upload → AI extraction → STR comparison → decision → report → PDF; its audit trail
holds `CASE_CREATED`, `DOCUMENT_UPLOADED`, `DOCUMENT_PROCESSED`, `DNA_COMPARED`,
`DECISION_GENERATED` and the report/PDF events). Demos B and C keep their comparison,
decision, report and audit evidence but have no document or extraction row — their STR
evidence was submitted straight to the comparison endpoint by earlier automated QA — so
their document and AI stages show the honest empty state ("No document submitted").
Present those two from the assessment/report view, or produce a fresh review-required
case live with the fixture below.

### Upload fixtures for the live walkthrough

`.qa-tmp/` is gitignored local QA scratch; both files are regenerable with
`python .qa-tmp/make_demo_fixture.py` and both are labelled synthetic on their face.

| Fixture | What the development mock provider extracts | Deterministic outcome |
| --- | --- | --- |
| `demo-synthetic-dna-report.pdf` (1 998 B) | the case identity's full 20-marker reference profile | `EXACT_MATCH` 20/20 → **VERIFIED** (100) |
| `demo-synthetic-dna-report-PARTIAL.pdf` (2 044 B) | the same profile minus `D22S1045` and `SE33` | `PARTIAL_MATCH` 18/20 (90 %) → **REVIEW_REQUIRED** |

The difference is driven by the `GV-PARTIAL` behaviour marker the mock reads in the
uploaded bytes (`backend/app/services/ai/mock.py`) — the STR engine, the 70/20/10
weighting and the decision rules are untouched, and rule 3 (`PARTIAL_MATCH` →
`REVIEW_REQUIRED`) still overrides the 90 % figure, which is exactly the "the score
never decides alone" point worth making to a judge. Both fixtures were verified
offline against the live reference profile (upload validator accepts them, `%PDF-`
header intact, 20/20 vs 18/20 extraction); they were not each re-run through the UI.

Note on those two rows: the mock reports the *registered* profile for them because
their marker table is not machine-readable (compressed content stream, and rows
printed as `NAME  alleles` without the `|` the reader expects), which is precisely
the documented "unreadable document → fall back to the reference" path. Reports
that carry a readable `NAME | allele, allele` table — such as the 50 files under
`.qa-tmp/verification-reports/` — are extracted from their own bytes instead, so
their differing alleles really do come out of the document.

### Files touched in Step 12 (presentation layer only)

| File | What it does now (as verified in the browser pass) |
| --- | --- |
| `frontend/src/hooks/useCaseOverview.ts` | Builds Command Center decision counts from `GET /verifications/{id}/decision` per assessable case (capped, with explicit coverage reporting) because no aggregate endpoint exists |
| `frontend/src/pages/DashboardPage.tsx` | Four headline statistics (cases / review required / verified / mismatch), a stated basis line for the counts, quick actions, pipeline reference and system status |
| `frontend/src/components/VerificationPipeline.tsx` | Eight-stage pipeline in reference and per-case variants, driven only by report/audit fields |
| `frontend/src/components/VerificationAssessmentSection.tsx` | One prominent result card per outcome plus the transparent evidence breakdown |
| `frontend/src/pages/VerificationCaseDetailPage.tsx` | Stage ordering header → pipeline → document → AI extraction → DNA analysis → evidence → audit → report, with expandable per-stage detail |

### Verification performed in Step 12

- Backend suite: **272 passed** (exit code 0) — unchanged from the Step 11 baseline,
  nothing skipped, weakened or deleted.
- `npm run build`: clean, 83 modules, `index-CoPW6-jc.js` 354.03 kB (gzip 102.27 kB)
  and `index-BMlhGk7Y.css` 47.78 kB (gzip 8.76 kB) in 12.84 s.
- Production bundle re-scanned: no API key, secret, token, password hash, database
  URL, filesystem path or `localhost:8000` string; the only `Bearer`/`password`
  occurrences are the runtime header template and the login form.
- Live HTTP battery against the running API: **92/92 checks** — every pipeline stage
  read over the stored cases, report-vs-stored-decision equality for all three
  outcomes, PDF header/size/embedded-text scan, 10 unauthenticated `401` probes,
  wrong-secret / expired / `alg:none` / malformed / wrong-scheme JWT rejection,
  foreign and unknown id `404`, path-traversal probes, malformed DNA `422`s,
  spoofed / disguised / empty / oversized upload rejections, and a response-body
  leakage scan.
- Full demo walkthrough in a browser, without developer tools: protected-route
  redirect before sign-in → login → Command Center → CNIC lookup → case → upload →
  AI extraction (20/20 markers) → DNA comparison (`EXACT_MATCH`) → evidence
  assessment (`VERIFIED` 100/100) → audit timeline → report → PDF download →
  logout → three protected routes redirect again. 23/23 network requests returned
  200 and the console showed **zero errors or warnings**.
- Responsive pass at 375 / 414 / 640 / 768 / 1024 / 1440 px across login, Command
  Center, workspace, case list, case detail, report and report library: 0 px
  document-level horizontal overflow on every screen, tables keep their intentional
  scroll containers, no tap target below 28 px, and the mobile menu opens, lists four
  links and hides at desktop width.
- Database: read-only checks only — no reset, no reseed, no deleted case, identity,
  profile or evidence row. Final counts: **123** identity records, **123** DNA
  profiles, **1** user, **24** verification cases, **7** documents, **7**
  extractions, **31** comparisons, **8** decisions, **41** audit events.
- Qwen readiness: configuration surface, factory behaviour (production refuses the
  mock; `AI_PROVIDER=qwen` without a key returns a safe `503`, never a fake result)
  and the provider tests were all verified. **No live Qwen call was made** — no
  `QWEN_API_KEY` is configured, so live Qwen remains PENDING.

## Final Submission & Release Verification (Step 13)

Step 13 changed **no source, schema, route, rule, engine or test file** — the
deterministic STR engine, the 70/20/10 scoring, the decision rules, the AI extraction
validation, the report/PDF path and the frontend architecture are exactly what Step 12
delivered. What Step 13 did was verify the assembled system as a submission, in thirteen
phases, and record the evidence. Every number below comes from a re-runnable script and
its captured output under `.qa-tmp/` (gitignored local QA scratch — never submitted).

### What Step 13 verified

| Area | Evidence | Result |
| --- | --- | --- |
| Submission inventory | `step13_submission_audit.txt` | 127 required source files classified A–F; 40 required files still **untracked**, 12 QA items staged by mistake — both reported, nothing deleted or unstaged |
| Secrets | `step13_secret_audit.txt` | PASS — no real credential, token or key in backend source, tests, frontend source, docs, the git index or the bundle; one by-design development placeholder tracked as a deployment-time action |
| Documentation accuracy | `step13_doc_review.txt` | every mounted endpoint, env var, panel marker, weight, rule, outcome, mandated disclaimer and demo case label cross-checked against code and database |
| Backend suite | `python -m pytest` | **272 passed**, exit 0 — no test skipped, weakened, deleted or rewritten |
| Production build | `npm run build` (`tsc -b && vite build`) | clean, 83 modules, `index-CoPW6-jc.js` 354.03 kB + `index-BMlhGk7Y.css` 47.78 kB; identical hashes before and after the pass |
| Bundle security | `step13_bundle_scan.py` | 14 prohibited categories clean (no `sk-` key, `QWEN_API_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`, real JWT, password hash, private path, baked-in `localhost:8000`); the Step 11 `VITE_API_BASE_URL`-else-same-origin `/api/v1` rule is intact |
| Full workflow | `step13_smoke.txt` — performed end to end in a real browser | **15/15 PASS**: sign-in → Command Center → CNIC lookup → case → upload → AI extraction (20/20) → STR comparison (`EXACT_MATCH`) → evidence (100/100) → `VERIFIED` → audit → report → PDF download → sign-out → protected-route redirect |
| Security regression | `step13_security.txt` | **170 live checks + 24 targeted tests, 0 failures**: `401`/`404`/`422`/`413` behaviour, tampered/expired/`alg:none`/wrong-scheme JWT, ownership, traversal, malformed and disguised uploads, response-body leakage |
| Database integrity (read-only) | `step13_db_integrity.txt` | **64 checks, 0 failures** — 123 identity records · 123 DNA profiles · 20-marker panel · all 25 cases present with no gap in the id sequence (10 draft, 6 in progress, 1 review required, 8 completed, the newest being `GV-2026-000025`, **VERIFIED** 100/100) · `integrity_check = ok` · `foreign_key_check` empty · FK enforcement active on the app engine · the 10 persisted foreign keys match the ORM exactly (6 `RESTRICT`, 4 `CASCADE`) · deletion protection proved behaviourally on a throwaway copy |
| Demo readiness | `STEP13_DEMO_CHECKLIST.md`, rehearsed by `step13_demo_preflight.txt` | **10/10** BEFORE-DEMO rows executed against the live stack; D1–D16 click path matches the real UI labels |

The only state the walkthrough deliberately added was its own case: `GV-2026-000025`
(Sami Demoosh, `EXACT_MATCH` 20/20 → **VERIFIED** 100/100), with one document, one
extraction, one comparison, one decision and seven audit events. Nothing was reset,
reseeded, cleaned or deleted to obtain it.

### Exact commands used

```
cd backend
./.venv/Scripts/python.exe -m pytest                     # 272 passed, exit 0
./.venv/Scripts/python.exe run.py                        # documented launcher; non-destructive create_all
./.venv/Scripts/python.exe ../.qa-tmp/step13_db_integrity.py    # read-only (mode=ro) + copy-based probes

cd frontend
npm run build                                            # tsc -b && vite build
npm run dev                                              # Vite on http://localhost:5173
```

Each QA script above was run from `backend/` with the project venv interpreter; the
browser phases were driven manually against `http://localhost:5173`.

### Interruption and recovery

The machine shut down unexpectedly part-way through Step 13. Recovery inspection showed
the working tree, git index, database, storage and every completed Phase 1–11 artifact
survived intact — the only loss was the two running dev processes. After restarting them,
the pass was re-verified rather than re-run from scratch: `pytest` (272 passed),
`npm run build` (identical bundle hashes), the bundle scan, and
`step13_postrecovery_check.txt` — **15 read-only live checks, 0 failures** — covering
health, `401` on an unauthenticated route, login, the 25-case list, the intact
`GV-2026-000025` report (aggregate-only DNA, 70/20/10 → `VERIFIED`, model labelled
`mock-document-intelligence`), a withheld reference panel on CNIC lookup, a forged JWT,
a traversal probe, and identical row counts plus a clean `integrity_check` before and
after. A browser session re-confirmed login → Command Center → lookup → case → report →
logout → protected-route redirect with zero console errors.

### Status of the external integrations

- **Live Qwen — PENDING.** No `QWEN_API_KEY` is configured (`backend/.env` carries it only
  as a comment) and `AI_PROVIDER` is unset, so `ai_provider` falls back to the `mock`
  development default. The provider abstraction, factory guards and validation were
  verified offline; **no live Qwen API request was made and none is claimed.** The key
  stays backend-only, never in a `VITE_*` variable, never logged and never returned.
- **Alibaba Cloud — NOT DEPLOYED.** Nothing was deployed to a cloud provider; no cloud
  resource was created, contacted or verified. The one-process target (browser → static
  frontend → HTTPS → FastAPI → SQLite → storage → Qwen) remains ready to host, with no
  Kubernetes, microservices, Redis or Celery introduced.
- **Docker — NOT BUILT OR RUN.** `backend/Dockerfile` exists but no Docker engine is
  available on this machine, so container behaviour is unverified.

### Known limitations carried forward

1. Document upload validation checks the magic bytes and size, not a full parse — a file
   with a valid `%PDF-` header and junk body is accepted (rejected later by extraction
   validation). Documented, not patched in Step 13.
2. The 40 required-but-untracked files and the 12 staged QA items listed in
   `step13_submission_audit.txt` are operator decisions for any future commit; Step 13
   made no commit and no push.
3. Twenty-two QA screenshots from Steps 4–11 sit in the repository root (not gitignored);
   they were left in place because Step 13 deletes nothing.

## Current Stage

**Step 10 — Command Center & UI Polish — COMPLETE.** The Command Center dashboard,
Quick Actions, the eight-stage pipeline, the report library, the restructured case
detail page, the standardized state blocks, the redesigned navigation with a
keyboard-accessible mobile menu, the accessibility and motion pass and the landing
copy are all in place, verified against the unchanged backend (244 tests).

**Step 11 — Deployment & Production Readiness — COMPLETE.** Environment-driven
configuration with production startup guards, a `PORT`-aware backend entrypoint
(`python run.py`), a non-destructive database/storage startup, an env-configurable
frontend API URL, a split runtime/test dependency manifest, an optional (unbuilt)
container image, a completed `.gitignore`, deployment tests (272 backend tests in
total) and the live end-to-end, security and production-bundle verification above.

**Step 12 — Final Integration, QA & Hackathon Demo Readiness — COMPLETE.** The
existing pipeline was verified end to end through both the API and the UI, the
demo-ready VERIFIED / REVIEW_REQUIRED / MISMATCH scenarios were identified, two
labelled synthetic upload fixtures were produced, the responsive matrix and the
security regression passed, and the only source changes were five presentation-layer
frontend files (272 backend tests and a clean production build unchanged).

**Step 13 — Final Submission & Release Readiness — COMPLETE.** A verification-only pass:
no source file changed. Submission inventory, secret audit, documentation accuracy, the
272-test suite, the production build, the bundle scan, a 15-item browser walkthrough, a
170-check security regression, 64 read-only database-integrity checks and a rehearsed
demo checklist all passed, and the pass was fully re-confirmed after an unexpected system
shutdown. Live Qwen remains PENDING, Alibaba Cloud is not deployed and Docker is not
built — none of those are claimed as done.

Nothing was deployed to a cloud provider and no real Qwen call was made; admin
management of identity/DNA records remains a separate, later stage.
