# Phase 6 — GeM Requirement Extraction

Purpose: Add a deterministic, rule-based requirement extraction layer for GeM-style tenders.

Architecture: Uses existing Phase 2 document text (pages), performs rule-based extraction and deterministic ID generation, preserves provenance, and exposes an API endpoint at `/api/v1/compliance/requirements/extract`.

Model: `Requirement` in `backend/app/compliance/models.py`.

Extraction: rule-based regex heuristics; deterministic IDs via SHA256(document_id|text).

Limitations: deterministic, rule-based, no external LLMs. Future phases may integrate semantic models.
