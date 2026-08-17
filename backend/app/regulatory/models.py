import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RegulatorySource(BaseModel):
    source_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    issuing_authority: str
    jurisdiction: str = "INDIA"
    government_level: str = "CENTRAL GOVERNMENT"
    source_type: str
    authority_level: str = "PRIMARY_GOVERNMENT_SOURCE"
    official_url: str = ""
    publication_date: str = ""
    effective_date: str = ""
    version: str = "UNKNOWN"
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "UNKNOWN"
    ingestion_status: str = "SOURCE_REQUIRED"
    content_hash: Optional[str] = None
    source_domain: str = "REGULATORY_AUTHORITY"


class RegulatoryDocument(BaseModel):
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    title: str
    issuing_authority: str
    jurisdiction: str = "INDIA"
    government_level: str = "CENTRAL GOVERNMENT"
    document_type: str = "OFFICIAL_DOCUMENT"
    version: str = "UNKNOWN"
    publication_date: str = ""
    effective_date: str = ""
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    official_url: str = ""
    content_hash: Optional[str] = None
    status: str = "UNKNOWN"
    ingestion_status: str = "SOURCE_REQUIRED"


class RegulatoryProvision(BaseModel):
    provision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    source_id: str
    parent_id: Optional[str] = None
    provision_type: str = "SECTION"
    provision_number: str = ""
    heading: str = ""
    text: str = ""
    raw_text: str = ""
    normalized_text: str = ""
    page_number: Optional[int] = None
    source_locator: Optional[str] = None
    official_url: str = ""
    content_hash: Optional[str] = None
    status: str = "ACTIVE"
    metadata: Dict[str, Any] = Field(default_factory=dict)
