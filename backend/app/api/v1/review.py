"""Review actions API: officer accept / override with mandatory reason (Plan Step 11, R4).

The officer decides, always: overrides require a written reason (HTTP 422
otherwise) and land in the hash-chained audit trail immediately.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.audit import service as audit_service
from app.compliance import phase8_service

router = APIRouter(prefix="/review", tags=["review"])

VALID_ACTIONS = {"ACCEPT", "OVERRIDE", "DISMISS", "COMMENT"}


class ReviewActionIn(BaseModel):
    actor: str
    action: str
    finding_id: str
    requirement_id: Optional[str] = None
    analysis_id: Optional[str] = None
    reason: str = ""
    comment: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewActionOut(BaseModel):
    review_id: str
    action: str
    finding_id: str
    status: str
    audit_event_id: str
    audit_event_hash: str


@router.post("/actions", response_model=ReviewActionOut)
def submit_review_action(payload: ReviewActionIn):
    action = payload.action.upper()
    if action not in VALID_ACTIONS:
        raise HTTPException(status_code=422, detail=f"action must be one of {sorted(VALID_ACTIONS)}")

    # R4: accept/override/dismiss are decisions - they require a written reason.
    if action in {"OVERRIDE", "DISMISS"} and not payload.reason.strip():
        raise HTTPException(
            status_code=422,
            detail="A written reason is required for OVERRIDE/DISMISS decisions.",
        )
    if action == "COMMENT" and not payload.comment.strip():
        raise HTTPException(status_code=422, detail="A comment is required for COMMENT action.")

    event = audit_service.append_event(
        actor=payload.actor,
        action=f"REVIEW_{action}",
        entity_type="finding",
        entity_id=payload.finding_id,
        payload={
            "requirement_id": payload.requirement_id,
            "analysis_id": payload.analysis_id,
            "reason": payload.reason.strip() or None,
            "comment": payload.comment.strip() or None,
            **payload.metadata,
        },
    )

    from uuid import uuid4

    return ReviewActionOut(
        review_id=str(uuid4()),
        action=action,
        finding_id=payload.finding_id,
        status="RECORDED",
        audit_event_id=event.event_id,
        audit_event_hash=event.event_hash,
    )


@router.get("/actions")
def list_review_actions(finding_id: Optional[str] = None, limit: int = 200):
    events = audit_service.read_chain(limit=limit, entity_id=finding_id)
    return [
        {
            "event_id": e.event_id,
            "actor": e.actor,
            "action": e.action,
            "entity_id": e.entity_id,
            "reason": e.payload.get("reason"),
            "comment": e.payload.get("comment"),
            "timestamp": e.timestamp.isoformat(),
            "event_hash": e.event_hash,
            "prev_hash": e.prev_hash,
        }
        for e in events
        if e.action.startswith("REVIEW_")
    ]
