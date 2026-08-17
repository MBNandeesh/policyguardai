"""
Retrieval chunk models for Phase 4.

Chunks are retrieval-ready representations of provisions with preserved provenance.
Every chunk is traceable back to its authoritative source provision.
"""

from typing import Any, Dict, List, Optional


class RetrievalChunk:
    """
    A retrieval-ready chunk of regulatory content.
    
    Chunks preserve all provenance information from the original provision.
    A chunk is a retrieval representation, NOT a replacement for the authoritative provision.
    
    Attributes:
        chunk_id: Unique identifier for this chunk.
        document_id: Reference to the regulatory document.
        source_id: Reference to the authoritative source.
        provision_id: Reference to the original provision.
        parent_provision_id: Optional reference to parent provision (for hierarchy).
        chunk_index: Position of this chunk within provision chunks (0-based).
        text: The chunk content (substring of provision text).
        normalized_text: Normalized version of chunk content.
        provision_number: Rule/section number from original provision.
        heading: Heading from original provision.
        page_number: Page reference from original provision.
        source_locator: Source-specific locator (e.g., "p.5", "section 2.3").
        official_url: Official URL of regulatory document.
        version: Version of the regulatory document.
        status: Status of the provision (ACTIVE, SUPERSEDED, etc.).
        content_hash: SHA256 hash of original provision text for integrity.
        metadata: Additional metadata preserved from provision.
        embedding_status: Status of embedding (PENDING, EMBEDDED, ERROR).
        vector: Optional embedded vector representation.
        created_at: ISO timestamp when chunk was created.
        retrieved_at: ISO timestamp when chunk was retrieved from storage.
    """

    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        source_id: str,
        provision_id: str,
        chunk_index: int,
        text: str,
        normalized_text: str,
        provision_number: str,
        heading: str,
        page_number: Optional[int],
        source_locator: Optional[str],
        official_url: str,
        version: str,
        status: str,
        content_hash: str,
        parent_provision_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding_status: str = "PENDING",
        vector: Optional[List[float]] = None,
        created_at: Optional[str] = None,
        retrieved_at: Optional[str] = None,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.source_id = source_id
        self.provision_id = provision_id
        self.parent_provision_id = parent_provision_id
        self.chunk_index = chunk_index
        self.text = text
        self.normalized_text = normalized_text
        self.provision_number = provision_number
        self.heading = heading
        self.page_number = page_number
        self.source_locator = source_locator
        self.official_url = official_url
        self.version = version
        self.status = status
        self.content_hash = content_hash
        self.metadata = metadata or {}
        self.embedding_status = embedding_status
        self.vector = vector
        self.created_at = created_at
        self.retrieved_at = retrieved_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary (for persistence)."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "provision_id": self.provision_id,
            "parent_provision_id": self.parent_provision_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "normalized_text": self.normalized_text,
            "provision_number": self.provision_number,
            "heading": self.heading,
            "page_number": self.page_number,
            "source_locator": self.source_locator,
            "official_url": self.official_url,
            "version": self.version,
            "status": self.status,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
            "embedding_status": self.embedding_status,
            "vector": self.vector,
            "created_at": self.created_at,
            "retrieved_at": self.retrieved_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RetrievalChunk":
        """Create chunk from dictionary (for persistence)."""
        return RetrievalChunk(
            chunk_id=data["chunk_id"],
            document_id=data["document_id"],
            source_id=data["source_id"],
            provision_id=data["provision_id"],
            chunk_index=data["chunk_index"],
            text=data["text"],
            normalized_text=data["normalized_text"],
            provision_number=data["provision_number"],
            heading=data["heading"],
            page_number=data.get("page_number"),
            source_locator=data.get("source_locator"),
            official_url=data["official_url"],
            version=data["version"],
            status=data["status"],
            content_hash=data["content_hash"],
            parent_provision_id=data.get("parent_provision_id"),
            metadata=data.get("metadata", {}),
            embedding_status=data.get("embedding_status", "PENDING"),
            vector=data.get("vector"),
            created_at=data.get("created_at"),
            retrieved_at=data.get("retrieved_at"),
        )


class RetrievalResult:
    """
    Result of a retrieval query.
    
    Contains chunk information and retrieval metadata (similarity score, rank, etc.).
    Every result is traceable to authoritative source.
    """

    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        source_id: str,
        provision_id: str,
        provision_number: str,
        heading: str,
        text: str,
        page_number: Optional[int],
        source_locator: Optional[str],
        official_url: str,
        version: str,
        status: str,
        content_hash: str,
        similarity_score: Optional[float] = None,
        rank: Optional[int] = None,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.source_id = source_id
        self.provision_id = provision_id
        self.provision_number = provision_number
        self.heading = heading
        self.text = text
        self.page_number = page_number
        self.source_locator = source_locator
        self.official_url = official_url
        self.version = version
        self.status = status
        self.content_hash = content_hash
        self.similarity_score = similarity_score
        self.rank = rank

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for API response."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "provision_id": self.provision_id,
            "provision_number": self.provision_number,
            "heading": self.heading,
            "text": self.text,
            "page_number": self.page_number,
            "source_locator": self.source_locator,
            "official_url": self.official_url,
            "version": self.version,
            "status": self.status,
            "content_hash": self.content_hash,
            "similarity_score": self.similarity_score,
            "rank": self.rank,
        }

    def citation_metadata(self) -> Dict[str, Any]:
        """
        Citation-ready metadata for this result.
        
        Contains all provenance information needed for citations.
        """
        return {
            "source_id": self.source_id,
            "document_id": self.document_id,
            "provision_id": self.provision_id,
            "provision_number": self.provision_number,
            "title": self.heading,
            "page_number": self.page_number,
            "source_locator": self.source_locator,
            "official_url": self.official_url,
            "version": self.version,
            "content_hash": self.content_hash,
        }
