"""Audit trail: append-only, hash-chained event log.

SIH26100 capability 14 and Plan R5: every verification, evaluation and officer
decision is recorded in an append-only, tamper-evident chain. Each entry is
chained to the previous entry's hash; the API exposes chain verification so
auditors can prove no event was inserted, altered or removed.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.config import settings

STORAGE_ROOT = os.path.join(settings.storage_path, "audit")

GENESIS_HASH = "0" * 64


class AuditEvent(BaseModel):
    event_id: str
    seq: int
    actor: str
    action: str
    entity_type: str
    entity_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    prev_hash: str
    event_hash: str


def _chain_path() -> str:
    return os.path.join(STORAGE_ROOT, "chain.jsonl")


def _compute_event_hash(
    *,
    seq: int,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: Dict[str, Any],
    timestamp: str,
    prev_hash: str,
) -> str:
    material = json.dumps(
        {
            "seq": seq,
            "actor": actor,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload,
            "timestamp": timestamp,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def append_event(
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    """Append one event to the chain. Append-only: no update or delete exists."""
    os.makedirs(STORAGE_ROOT, exist_ok=True)
    path = _chain_path()

    seq = 1
    prev_hash = GENESIS_HASH
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            lines = [line for line in handle if line.strip()]
        if lines:
            last = json.loads(lines[-1])
            seq = last["seq"] + 1
            prev_hash = last["event_hash"]

    timestamp = datetime.now(timezone.utc)
    timestamp_iso = timestamp.isoformat()
    event_hash = _compute_event_hash(
        seq=seq,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
        timestamp=timestamp_iso,
        prev_hash=prev_hash,
    )
    event = AuditEvent(
        event_id=f"evt-{seq:06d}",
        seq=seq,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
        timestamp=timestamp,
        prev_hash=prev_hash,
        event_hash=event_hash,
    )
    # Persist with the exact timestamp string used in the hash material, so
    # re-verification reproduces the hash byte-for-byte.
    record = event.model_dump(mode="json")
    record["timestamp"] = timestamp_iso
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return event


def read_chain(limit: int = 200, entity_id: Optional[str] = None) -> List[AuditEvent]:
    path = _chain_path()
    if not os.path.exists(path):
        return []
    events: List[AuditEvent] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            if entity_id and data.get("entity_id") != entity_id:
                continue
            events.append(AuditEvent.model_validate(data))
    if entity_id:
        return events[-limit:]
    return events[-limit:]


def verify_chain() -> Dict[str, Any]:
    """Recompute the whole chain and report the first inconsistency, if any."""
    path = _chain_path()
    if not os.path.exists(path):
        return {"valid": True, "events": 0, "head_hash": GENESIS_HASH, "broken_at": None}

    prev_hash = GENESIS_HASH
    count = 0
    head_hash = GENESIS_HASH
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            expected_hash = _compute_event_hash(
                seq=data["seq"],
                actor=data["actor"],
                action=data["action"],
                entity_type=data["entity_type"],
                entity_id=data["entity_id"],
                payload=data.get("payload", {}),
                timestamp=data["timestamp"],
                prev_hash=prev_hash,
            )
            if data["prev_hash"] != prev_hash or data["event_hash"] != expected_hash:
                return {
                    "valid": False,
                    "events": count,
                    "head_hash": head_hash,
                    "broken_at": data["seq"],
                }
            prev_hash = data["event_hash"]
            head_hash = data["event_hash"]
            count += 1
    return {"valid": True, "events": count, "head_hash": head_hash, "broken_at": None}
