# PolicyGuard AI - Architecture (Phase 0)

## System Components

- Frontend: Next.js + TypeScript + Tailwind — lightweight dashboard shell and client for API calls.
- Backend: FastAPI (Python 3.12.x) — API endpoints, configuration, logging, and future AI integration.
- Data: PostgreSQL for relational data; vector database (Qdrant or pgvector) for retrieval.
- Storage: Local or object storage for uploaded documents.
- AI: Configurable provider (cloud API during development; self-hosted weights for on-prem).

## Data Flow (high-level)

1. Officer uploads PDF via the frontend.
2. Backend ingests document, stores original file, extracts layout-aware text and metadata.
3. Extracted content is chunked and indexed into vector DB.
4. RAG pipeline retrieves relevant regulations from knowledge base and supports compliance checks.
5. Findings, evidence, and audit trail are stored in relational DB and returned to the frontend.

## Frontend / Backend Interaction

- REST API over `/api/v1/*`.
- Frontend calls health endpoint for startup checks: `GET /api/v1/health`.
- Future: file upload endpoints, findings review endpoints, and report generation endpoints.

## AI Pipeline (future)

- Document parsing (layout-aware), OCR fallback, table extraction.
- Indexing to vector DB with metadata (page numbers, bounding boxes).
- RAG search against curated regulations (only those present in KB).
- Validation and programmatic checks before surfacing findings.

## Deployment Strategy (Phase 0)

- Docker Compose for local development (backend, postgres, qdrant).
- Environment vars via `.env`.
- CI to run tests and linting before merges.
