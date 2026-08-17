from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid


class BoundingBox(BaseModel):
    x1: Optional[float] = None
    y1: Optional[float] = None
    x2: Optional[float] = None
    y2: Optional[float] = None


class PageBlock(BaseModel):
    text: str
    bbox: Optional[List[float]] = None


class PageElement(BaseModel):
    element_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    page_number: int
    type: str
    text: str = ""
    bbox: Optional[BoundingBox] = None
    confidence: Optional[float] = None
    reading_order: int = 0
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Page(BaseModel):
    document_id: str
    page_number: int
    text: str
    extraction_method: str
    ocr_required: bool = False
    processing_status: str = "processed"
    blocks: List[PageBlock] = Field(default_factory=list)
    elements: List[PageElement] = Field(default_factory=list)


class DocumentRecord(BaseModel):
    document_id: str
    filename: str
    file_size: int
    upload_time: datetime
    page_count: int = 0
    processing_status: str = "processing"
    processing_error: Optional[str] = None
    extraction_method: str = "text"
    created_at: datetime
