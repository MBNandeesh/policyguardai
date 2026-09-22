"""Audit API: append events, read the chain, verify integrity.

Read access to the event chain stays public so the frontend audit trail can
render without a session; any event *writing* or chain *verification* is
restricted to authenticated officers so the tamper-evident chain cannot be
polluted or probed by anonymous callers.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.v1.auth import require_officer
from app.audit import service as audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEventIn(BaseModel):
    actor: str
    action: str
    entity_type: str
    entity_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)


@router.post("/events")
def append_event(payload: AuditEventIn, officer: Dict[str, Any] = Depends(require_officer)):
    # The authenticated officer identity is authoritative for audit writes.
    event = audit_service.append_event(
        actor=officer["officer_id"],
        action=payload.action,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        payload=payload.payload,
    )
    return event.model_dump(mode="json")


@router.get("/events")
def list_events(limit: int = 200, entity_id: Optional[str] = None):
    events = audit_service.read_chain(limit=limit, entity_id=entity_id)
    return [e.model_dump(mode="json") for e in events]


@router.get("/verify")
def verify_chain(officer: Dict[str, Any] = Depends(require_officer)):
    """Tamper-evidence check: recompute the full hash chain."""
    return audit_service.verify_chain()
