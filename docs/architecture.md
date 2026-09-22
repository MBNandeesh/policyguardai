# PolicyGuard AI — System Architecture

## System Components

- **Frontend:** Next.js + TypeScript + Tailwind — officer portal (login, upload,
  compliance dashboard, review queue, reports with PDF download, audit trail view).
- **Backend:** FastAPI (Python 3.12) — auth, document ingestion with OCR, compliance
  engine, regulatory grounding, retrieval, verification adapters, review workflow,
  hash-chained audit ledger, health reporting.
- **Storage:** JSON file store (`STORAGE_PATH`) for documents, analyses, reports and
  the audit chain. Reserved for future migration: PostgreSQL (relational) and a
  vector database (Qdrant or pgvector).
- **OCR:** Tesseract installed inside the backend Docker image (guaranteed available
  in production; optional locally for scanned-PDF testing).
- **AI:** Deterministic/rule-based pipeline today (see "What is actually AI vs
  deterministic logic" in the root README). The retrieval/embedding layer exposes a
  provider abstraction so a semantic embedding model can be swapped in later.

## Data Flow (end-to-end)

1. Officer logs in (HMAC-signed session token; protected endpoints require it).
2. Officer uploads tender/bidder PDF via the frontend; the frontend attaches the
   bearer token to every request, including multipart uploads.
3. Backend ingests the document, stores the original, extracts text page by page
   (pypdf, with Tesseract OCR fallback for scanned pages) and records provenance
   (page count, text per page, content hashes).
4. The compliance engine extracts requirements from the tender (rule-based,
   categorized, mandatory/optional with confidence), then maps each requirement
   against bidder page evidence in a paired analysis.
5. Each requirement is grounded against the regulatory registry: a retrieval hit
   only becomes authoritative evidence if its source, provision number, official
   URL and content hash all validate against registered records.
6. Findings, per-requirement assessments, and the aggregated report are persisted
   and surfaced in the frontend; items needing judgment are escalated to the
   officer review queue.
7. The officer records a decision (approved / rejected / needs-info) attributed to
   their authenticated identity; the decision and every workflow step are appended
   to the hash-chained audit ledger.
8. The officer can download the report as a backend-generated PDF (ReportLab)
   containing the actual report data and the Responsible-AI disclaimer.

## Frontend / Backend Interaction

- REST API over `/api/v1/*`; the Next.js server proxies to the backend via
  `BACKEND_API_URL`.
- Public endpoints: `GET /api/v1/health` (also reports OCR capability).
- All sensitive operations (upload, analysis, decisions, report download, audit
  write/verify) require the officer bearer token.

## AI / Analysis Pipeline

- Deterministic rule-based requirement extraction (signals, categories, evidence
  types) — honest baseline, no generative model in the loop.
- Deterministic hash-based embedding + local vector store for regulatory retrieval,
  behind a provider abstraction ready for a real embedding model.
- Validation and programmatic checks before any finding is surfaced; anything
  unproven becomes `INSUFFICIENT_EVIDENCE` and escalates to human review.

## Deployment Strategy

- Backend: Render, Docker runtime (Tesseract guaranteed in the image); container
  honors the injected `PORT`.
- Frontend: Vercel (Next.js).
- Docker Compose for local development; environment variables via `.env`
  (see `.env.example`); production requires `POLICYGUARD_AUTH_SECRET`,
  `POLICYGUARD_DEMO_PASSWORD` and `POLICYGUARD_CORS_ORIGINS`.
- CI/local: `pytest` for the backend, `node frontend/__tests__/logic.test.mjs` for
  frontend logic tests.
