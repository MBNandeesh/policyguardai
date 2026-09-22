# PolicyGuard AI — AI-Powered Integrated Bid Compliance Verification Platform for GeM Procurement

PolicyGuard AI is a web platform that helps procurement officers evaluate bidder
submissions against tender requirements for GeM (Government e-Marketplace) style
procurement. Officers upload a tender PDF and bidder PDFs, the platform extracts
requirements from the tender, maps each requirement to evidence in the bidder
submission, classifies compliance status and risk, grounds findings in validated
regulatory provisions, and produces a downloadable compliance report — with every
final decision made by an authorized human officer and every action recorded in a
tamper-evident audit trail.

> **Responsible AI at a glance:** All AI/automated analysis is **advisory only**.
> The final procurement decision always remains with the authorized officer.

---

## Problem statement (Smart India Hackathon alignment)

Bid compliance checking in public procurement is manual, slow and error-prone.
Officers must compare long tender documents against bidder submissions line by line,
identify which requirements are mandatory, locate supporting evidence, and confirm
regulatory grounds — often across hundreds of pages. Missed requirements or
unverified claims lead to ineligible bidders slipping through, disputes, and delays.

PolicyGuard AI addresses **SIH problem theme: AI-powered automation of government
procurement compliance (GeM)** by automating the *tedious, mechanical* parts of this
review while deliberately keeping the *judgmental* parts with a human officer.

## Solution overview

The platform is a two-tier web application:

- **Frontend (Next.js + TypeScript)** — officer portal: login, document upload,
  compliance dashboard, review queue, reports, and decision workflow.
- **Backend (FastAPI + Python)** — document ingestion with OCR, deterministic
  requirement extraction, tender→bidder evidence mapping, compliance evaluation,
  regulatory retrieval with strict provenance validation, verification adapters,
  officer decisioning, and a hash-chained audit ledger.

Nothing is evaluated without traceable evidence: every finding cites the exact page
and text of the documents it came from, and every regulatory reference is validated
against an internal registry of official source documents before it can ground a
finding.

## Key features

| Feature | Status in this build |
|---|---|
| Tender & bidder PDF upload (text + scanned, via OCR) | ✅ Working |
| Rule-based requirement extraction (categorized, mandatory/optional) | ✅ Working |
| Tender → bidder evidence mapping | ✅ Working |
| Compliance analysis with status/risk classification | ✅ Working |
| Regulatory grounding with provenance + content-hash validation | ✅ Working |
| Verification adapters (MOCK / DOCUMENT modes, honestly labelled) | ✅ Working (no LIVE portals) |
| Human-review escalation for insufficient evidence | ✅ Working |
| Officer login / session tokens / protected endpoints | ✅ Working |
| Officer decision recording with audit chain | ✅ Working |
| Compliance report viewing + PDF download | ✅ Working |
| Tamper-evident audit trail (hash-chained) | ✅ Working |
| Live government portal integration | ❌ Not implemented (see honest limits below) |
| Autonomous procurement decisions | ❌ Never — by design |

## End-to-end workflow

```
1. Officer logs in                        (POST /api/v1/auth/login)
2. Tender PDF upload                      (POST /api/v1/documents/upload)
3. Bidder PDF upload                      (POST /api/v1/documents/upload)
4. Requirement extraction from tender     (POST /api/v1/compliance/extract)
5. Paired compliance analysis             (POST /api/v1/compliance/paired-analysis)
   tender requirements × bidder evidence
6. Compliance report generated            (GET /api/v1/compliance/report/{id})
7. Human-review queue for escalations     (GET /api/v1/review/queue)
8. Officer decision                       (POST /api/v1/review/...)
9. Download report as PDF                 (GET /api/v1/compliance/report/{id}/download)
10. Every step appended to audit chain    (GET /api/v1/audit/events)
```

## System architecture

```
┌──────────────────────┐        ┌───────────────────────────────────────────┐
│  Next.js frontend    │  HTTP  │  FastAPI backend                          │
│  (Vercel)            │──────▶ │  (Render, Docker runtime)                 │
│                      │ proxy  │                                           │
│  • Login (officer)   │ /api/* │  • auth (session tokens, HMAC-signed)     │
│  • Documents upload  │        │  • documents (PDF/OCR ingestion)          │
│  • Compliance views  │        │  • compliance (extraction, analysis,      │
│  • Review queue      │        │    paired mapping, reports)               │
│  • Reports + PDF dl  │        │  • regulatory (source registry, grounded) │
│  • Audit trail view  │        │  • retrieval (embedding + vector search)  │
└──────────────────────┘        │  • verification (MOCK/DOCUMENT adapters)  │
                                │  • review (officer decisions)             │
                                │  • audit (hash-chained event ledger)      │
                                │  • health (public, OCR capability)        │
                                └───────────────┬───────────────────────────┘
                                                │
                                       JSON file storage (STORAGE_PATH)
                                       + Tesseract OCR (in Docker image)
```

### What is actually AI vs deterministic logic

This section is deliberately honest. Judges should know exactly what each component does.

| Component | Implementation | Honest classification |
|---|---|---|
| PDF text extraction | `pypdf` for text PDFs | Deterministic |
| Scanned-PDF OCR | Tesseract (via `pytesseract`) in the Docker image | Deterministic (classic OCR) |
| Requirement extraction | Regex/keyword rules, category classifiers, mandatory-signal detection | **Deterministic / rule-based** |
| Tender→bidder evidence mapping | Deterministic matching over extracted requirements and document pages | Deterministic |
| Compliance status & risk classification | Rule engine over evidence presence, mandatory flags, explicit non-compliance patterns | **Deterministic / rule-based** |
| Regulatory retrieval | `DeterministicTestEmbedding` (hash-based, 384-dim) + local vector store, with strict provenance validation (source, provision number, official URL, content hash) | **Deterministic embedding abstraction** — pluggable interface exists for real embedding models, but the current provider is a deterministic hash, not a semantic model |
| Verification adapters | `MOCK` (deterministic, demo-sentinel driven) and `DOCUMENT` (checks for uploaded supporting document) modes only | **MOCK / DOCUMENT** — no adapter performs a live portal call in this build |
| Human-in-the-loop decisioning | Officer UI + review queue | Human judgment, not AI |

There is **no generative-LLM component in the analysis pipeline** in this build.
The retrieval/embedding layer is architected so a real embedding provider can be
substituted without changing downstream code, but until that is swapped in,
retrieval quality should be treated as deterministic-baseline, not semantic.

## Compliance engine

1. **Extraction** — the tender document is split page by page; sentences containing
   requirement signals (`shall`, `must`, `mandatory`, `bidder must submit`,
   `proof of`, `minimum`, etc.) become `Requirement` records with:
   - category (tax, financial, experience, msme, oem_authorization, …),
   - mandatory vs optional (strong/weak signal scoring),
   - expected evidence types (GST certificate, Udyam certificate, turnover proof, …),
   - full provenance (document id, page, section, exact source text, deterministic
     requirement id).
2. **Paired analysis** — each tender requirement is mapped against the bidder
   submission's page evidence. Statuses produced:
   `COMPLIANT`, `POTENTIAL_NON_COMPLIANCE`, `INSUFFICIENT_EVIDENCE`,
   `REQUIRES_REVIEW`, `NOT_APPLICABLE`.
   Risk severity is `HIGH` / `MEDIUM` / `LOW` / `UNKNOWN`, and any status other than
   a clean pass either escalates to human review or is explicitly marked
   not-applicable — the engine never silently approves a mandatory gap.
3. **Reports** — the `RequirementReport` aggregates counts, summary and per-requirement
   assessments. Reports are viewable in the UI and downloadable as a backend-generated
   PDF (ReportLab) containing the actual report data.

## Regulatory evidence & provenance

Regulatory grounding follows a strict chain:

```
Source (REGULATORY_AUTHORITY domain, official URL)
  └── Document (registered regulation, content hash)
        └── Provision (number, normalized text, official URL)
              └── Retrieval hit → validated against the provision record
```

A retrieved chunk can only ground a finding if:
- it resolves to a registered Phase-3 regulatory record,
- its exact text is contained in the provision's normalized text,
- provision number, official URL and content hash all match the registry.

If any check fails, or no validated evidence exists, the finding is marked
`INSUFFICIENT_EVIDENCE` and routed to human review. **The system never invents
legal text, rule numbers or URLs** — every citation is verifiable against the
internal registry, and the registry entries carry official URLs for manual follow-up.

## Responsible AI approach

- **Advisory only.** All automated analysis is decision support. No automated or
  AI-generated output ever approves or rejects a bid.
- **Human-in-the-loop by construction.** Mandatory requirements without clear
  evidence, insufficient-evidence findings, and potential non-compliances are all
  forced into the review queue. The engine cannot produce a final decision.
- **Evidence over inference.** Findings require document evidence; regulatory
  findings require validated authoritative provenance (see above).
- **No fabricated grounding.** No invented legal citations, rule numbers or URLs.
- **Honest capability labelling.** Verification results carry a `mode` field
  (`MOCK` / `DOCUMENT`) everywhere — the UI, the API and the PDF report. Simulated
  checks are explicitly marked "not an authoritative portal response" and are
  capped at the lowest trust tier. There is no adapter labelled LIVE, because none
  performs a live portal call.
- **Traceability.** Every finding, decision and report is linked to document pages,
  content hashes, officer identity, and an audit-chain event.

### Human-in-the-loop & officer decision workflow

When analysis produces `REQUIRES_REVIEW`, `INSUFFICIENT_EVIDENCE` or
`POTENTIAL_NON_COMPLIANCE`, the item appears in the officer review queue. The
officer sees the requirement, the mapped evidence, the regulatory basis, and the
system's explanation, then records a decision (`approved` / `rejected` /
`needs-info`) with an optional reason. The decision is attributed to the
authenticated officer (never to "the AI"), timestamped, and appended to the audit
chain. Until an officer decides, the report's overall status stays in review.

### Audit trail

Audit events form a **hash chain**: each event includes the hash of the previous
event, so any retroactive tampering breaks the chain and is detectable via the
verification endpoint. Events record actor, action, entity, reason, and timestamp.
The frontend scopes displayed events to the currently viewed report, and event
verification is officer-authenticated.

## Deployment architecture

| Tier | Platform | Notes |
|---|---|---|
| Frontend | Vercel (Next.js) | Proxies `/api/v1/*` to the backend via `BACKEND_API_URL` |
| Backend | Render, **Docker runtime** | `backend/Dockerfile` installs Tesseract OCR, so scanned-PDF OCR is guaranteed in production. The container honors Render's injected `PORT`. |
| Storage | Render disk / `/tmp` volume | JSON file store (`STORAGE_PATH`) for documents, analyses, reports, audit chain |
| OCR | Tesseract inside the backend image | Health endpoint reports OCR availability (`/api/v1/health` → `ocr.available`) |

## Local setup

Prerequisites: Python 3.12, Node.js 18+.

```bash
# Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   |   POSIX: source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env            # fill in the security variables
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
cp .env.example .env.local         # BACKEND_API_URL=http://localhost:8000
npm run dev                        # http://localhost:3000
```

Install Tesseract locally for scanned-PDF testing:
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- Debian/Ubuntu: `sudo apt install tesseract-ocr`

The health endpoint reports whether OCR was found; text PDFs work without it.

## Production deployment

See [DEPLOY.md](DEPLOY.md) for the full Render + Vercel walkthrough. Summary:

1. **Backend** — deploy `render.yaml` as a Render Blueprint (Docker runtime).
   Set `APP_ENV=production`, `POLICYGUARD_AUTH_SECRET`, `POLICYGUARD_DEMO_PASSWORD`,
   `POLICYGUARD_CORS_ORIGINS` (your Vercel URL), `STORAGE_PATH=/tmp/storage`.
   The backend refuses to start in production without the secret variables.
2. **Frontend** — deploy `frontend/` to Vercel with `BACKEND_API_URL` pointing at
   the Render URL (no trailing slash, no `/api/v1`).

## Environment variables

All variables are documented with examples in `.env.example` (backend) and
`frontend/.env.example` (frontend).

| Variable | Required | Purpose |
|---|---|---|
| `POLICYGUARD_AUTH_SECRET` | **Yes in production** | HMAC signing key for officer session tokens. No known fallback is ever used in production. |
| `POLICYGUARD_DEMO_PASSWORD` | **Yes in production** | Password for the seeded `officer-001` demo account. Development fallback: `officer123`. |
| `POLICYGUARD_CORS_ORIGINS` | Yes in production | Comma-separated allowed browser origins. `*` is refused in production. |
| `APP_ENV` | — | `development` (default) or `production`; enables strict validation. |
| `STORAGE_PATH` | — | File-store root. Production default `/tmp/storage` on Render. |
| `BACKEND_API_URL` (frontend) | Yes | Backend base URL for the Next.js `/api/v1` proxy. |

## Demo flow (SIH judging)

1. Open the deployed frontend → **Login** as `officer-001` with the demo password.
2. **Documents** → upload a tender PDF, then a bidder PDF.
3. **Compliance** → run extraction, then paired analysis for the bidder against the tender.
4. Open the generated **Report** → review statuses, risk, evidence, regulatory grounding.
5. **Review** → work the escalated queue, record an officer decision with a reason.
6. **Reports** → click **Download Report** to get the backend-generated PDF
   (includes the disclaimer that AI analysis is advisory only).
7. **Audit** → observe the hash-chained trail of every step, scoped per report,
   with officer identity on decisions.

Demo sentinels: identifiers containing `EXPIRED`, `MISMATCH` or `NOTFOUND`
reproduce verification failure scenarios deterministically (labelled MOCK).

## Testing

```bash
# Backend (pytest, 160+ tests)
cd backend && .venv/Scripts/python.exe -m pytest tests -q      # Windows
cd backend && .venv/bin/python -m pytest tests -q              # POSIX

# Frontend (dependency-free Node tests)
node frontend/__tests__/logic.test.mjs
```

Coverage highlights: end-to-end tender→analysis→decision→report→PDF flow, endpoint
authentication guards (401 vs 200), CORS production refusal of `*`, PDF report
content (report id, statuses, requirements, disclaimer), audit chain scoping and
tamper detection, frontend audit-scope filtering and API auth-header behaviour.

## Known limitations (honest)

- **Requirement extraction and compliance evaluation are deterministic/rule-based.**
  They reliably catch well-formed requirements but will miss unusually phrased ones.
- **Retrieval uses a deterministic hash embedding**, not a semantic embedding model.
  Matches are validated for provenance but similarity is lexical-baseline quality.
- **No live government portal integration.** All verification adapters are MOCK or
  DOCUMENT mode and are labelled as such. GST/MCA/Udyam/debarment results are
  simulated and never authoritative.
- **File-based storage.** The JSON store suits the SIH demo but not concurrent
  multi-user production; a database adapter is the natural next step.
- **Ephemeral free-tier disk.** Render's free `/tmp` storage resets on restart;
  documents must be re-uploaded after a redeploy.
- **Fairness properties are documented by design, not empirically benchmarked.**
  We do not claim formal fairness guarantees or certifications.
- **Single demo officer role** — no role hierarchy or multi-tenant org structure yet.

## Future enhancements

- Swap in a real semantic embedding provider (the retrieval interface is ready).
- LIVE verification adapters behind signed agreements with official portals
  (GSTN, MCA, Udyam) — the adapter contract and trust tiers already support this.
- LLM-assisted extraction as an *optional, audited* layer alongside the rule engine.
- Database-backed storage with retention policies and encrypted at-rest storage.
- Role-based access control beyond the single demo officer.
- Multilingual OCR and requirement extraction (English-first today).

## License

For Smart India Hackathon evaluation use.
