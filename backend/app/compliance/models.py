from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib


class Requirement(BaseModel):
    requirement_id: str
    title: str
    description: str
    category: str
    mandatory: bool
    evidence_required: bool = True
    evidence_types: List[str] = Field(default_factory=list)
    source_document_id: Optional[str] = None
    source_page: Optional[int] = None
    source_section: Optional[str] = None
    source_text: Optional[str] = None
    regulatory_reference: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


def deterministic_requirement_id(document_id: str, text: str) -> str:
    payload = f"{document_id}|{(text or '').strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
