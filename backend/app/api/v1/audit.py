"""Audit API: append events, read the chain, verify integrity."""

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.audit import service as audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEventIn(BaseModel):
    actor: str
    action: str
    entity_type: str
    entity_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)


@router.post("/events")
def append_event(payload: AuditEventIn):
    event = audit_service.append_event(
        actor=payload.actor,
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
def verify_chain():
    """Tamper-evidence check: recompute the full hash chain."""
    return audit_service.verify_chain()
