# PolicyGuard AI - Phase 5: Grounded Compliance Analysis

## Scope

Phase 5 creates a compliance-analysis foundation for procurement documents. It is document intelligence and compliance assistance, not legal advice or a legally binding decision engine. Findings use qualified language and are marked for human review.

## Flow

1. A processed Phase 2 user document supplies page-level document evidence.
2. The extracted document text is passed to the existing Phase 4 retrieval service as a query.
3. Retrieval returns active regulatory chunks from the Phase 3 knowledge base.
4. Each returned chunk is resolved back to its Phase 3 source, document, and provision.
5. The service persists an analysis and findings under the separate compliance storage area.

User document evidence and regulatory evidence are separate models and fields. A user document is never indexed as a regulation or promoted to regulatory authority.

## Grounding and Validation

Regulatory evidence is accepted only when its `source_id`, `document_id`, and `provision_id` resolve through Phase 3, their relationships agree, the source is a regulatory authority, and the retrieved text, provision number, official URL, and content hash agree with the authoritative record. Unsupported or fabricated citations are rejected.

Grounded statuses require regulatory basis. `INSUFFICIENT_EVIDENCE`, `UNKNOWN`, `NOT_APPLICABLE`, and `REQUIRES_REVIEW` may explicitly have no regulatory basis. Missing authority produces `INSUFFICIENT_EVIDENCE` with `source_required` provenance rather than an invented rule.

## API

### `POST /api/v1/compliance/analyze`

Request:

```json
{
  "document_id": "uploaded-phase-2-document-id",
  "requested_scope": "bid evaluation",
  "top_k": 5
}
```

The response contains the analysis, findings, page evidence, retrieved regulatory evidence, provenance, confidence, severity, and `requires_human_review`.

### `GET /api/v1/compliance/analyses/{analysis_id}`

Returns the persisted analysis and all findings.

### `GET /api/v1/compliance/analyses/{analysis_id}/findings`

Returns the findings for a persisted analysis.

## Limitations and Phase 6 Deferrals

The current deterministic foundation does not make automatic legal conclusions, calculate a final compliance score, generate recommendations, produce audit reports, automate workflows, send notifications, provide dashboards, submit to government systems, or include production deployment. Those capabilities are deferred to later phases. An LLM provider abstraction can be added later, but any provider must reason only over document evidence and validated retrieved authority; it cannot become the source of truth.

No web scraper or unofficial GFR content is used. This phase uses only authoritative regulatory records already present in the Phase 3 store.