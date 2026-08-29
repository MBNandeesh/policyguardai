"""
Retrieval service for Phase 4 - orchestrates chunking, embedding, and indexing.

Coordinates:
1. Chunking of regulatory provisions.
2. Embedding of chunks.
3. Vector storage and indexing.
4. Similarity search and retrieval.
5. Metadata filtering.
6. Provenance preservation.
"""

import os
from typing import Any, Dict, List, Optional

from app.regulatory.service import (
    get_document,
    get_provision,
    get_source,
    list_documents,
    list_provisions,
    list_sources,
)
from app.retrieval.chunking import ChunkingStrategy, chunk_all_provisions
from app.retrieval.embedding_provider import EmbeddingProvider, get_embedding_provider
from app.retrieval.models import RetrievalChunk, RetrievalResult
from app.retrieval.vector_store import VectorStore, get_vector_store


class RetrievalService:
    """
    Orchestrates regulatory retrieval.
    
    Responsibilities:
    - Chunk regulatory provisions deterministically.
    - Embed chunks using configurable provider.
    - Store and search vectors.
    - Filter by metadata (jurisdiction, status, etc.).
    - Preserve and return provenance.
    - Prevent version mixing (ACTIVE vs SUPERSEDED).
    """

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        vector_store: Optional[VectorStore] = None,
        max_chunk_size: int = 1000,
    ):
        """
        Initialize retrieval service.
        
        Args:
            embedding_provider: Embedding provider (defaults to deterministic test).
            vector_store: Vector store backend (defaults to local).
            max_chunk_size: Maximum chunk size for chunking.
        """
        self.embedding_provider = embedding_provider or get_embedding_provider("deterministic")
        self.vector_store = vector_store or get_vector_store("local")
        self.chunking_strategy = ChunkingStrategy(max_chunk_size=max_chunk_size)

    def build_index(self) -> Dict[str, Any]:
        """
        Build/rebuild the retrieval index from all regulations.
        
        Process:
        1. Load all provisions from Phase 3.
        2. Chunk each provision.
        3. Embed each chunk.
        4. Store in vector database.
        
        Handles duplicates gracefully (upsert).
        
        Returns:
            Stats dict with counts.
        """
        # Load regulatory data
        provisions = list_provisions()
        documents = {doc["document_id"]: doc for doc in list_documents()}
        sources = {src["source_id"]: src for src in list_sources()}

        if not provisions:
            return {
                "status": "empty",
                "provisions": 0,
                "chunks": 0,
                "embedded": 0,
                "stored": 0,
            }

        # Chunk all provisions
        chunks = chunk_all_provisions(provisions, documents, sources, self.chunking_strategy.max_chunk_size)

        if not chunks:
            return {
                "status": "no_chunks",
                "provisions": len(provisions),
                "chunks": 0,
                "embedded": 0,
                "stored": 0,
            }

        # Embed and store chunks
        embedded_count = 0
        stored_count = 0

        for chunk in chunks:
            try:
                # Embed chunk text
                embedding = self.embedding_provider.embed_text(chunk.text)

                # Prepare metadata for vector store
                metadata = {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "source_id": chunk.source_id,
                    "provision_id": chunk.provision_id,
                    "provision_number": chunk.provision_number,
                    "heading": chunk.heading,
                    "text": chunk.text,
                    "page_number": chunk.page_number,
                    "source_locator": chunk.source_locator,
                    "official_url": chunk.official_url,
                    "version": chunk.version,
                    "status": chunk.status,
                    "content_hash": chunk.content_hash,
                    **chunk.metadata,
                }

                # Store in vector database
                self.vector_store.upsert(chunk.chunk_id, embedding, metadata)

                embedded_count += 1
                stored_count += 1
            except Exception as e:
                # Log error but continue with other chunks
                continue

        return {
            "status": "indexed",
            "provisions": len(provisions),
            "chunks": len(chunks),
            "embedded": embedded_count,
            "stored": stored_count,
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        status_filter: Optional[List[str]] = None,
        jurisdiction_filter: Optional[List[str]] = None,
        source_type_filter: Optional[List[str]] = None,
    ) -> List[RetrievalResult]:
        """
        Search for relevant regulatory provisions.
        
        Query processing:
        1. Embed query text.
        2. Search vector store with optional filters.
        3. Resolve metadata to complete provenance.
        4. Return ranked results.
        
        Filters:
        - status_filter: List of statuses (default: ["ACTIVE"])
        - jurisdiction_filter: List of jurisdictions (e.g., ["INDIA"])
        - source_type_filter: List of source types
        
        Returns:
            List of RetrievalResult objects, ranked by similarity.
        """
        if not query or not query.strip():
            return []

        if top_k <= 0:
            return []

        # Default to ACTIVE provisions only (version safety)
        if status_filter is None:
            status_filter = ["ACTIVE"]

        # Build filters dict
        filters: Dict[str, Any] = {}
        if status_filter:
            filters["status"] = status_filter
        if jurisdiction_filter:
            filters["jurisdiction"] = jurisdiction_filter
        if source_type_filter:
            filters["source_type"] = source_type_filter

        # Embed query
        try:
            query_embedding = self.embedding_provider.embed_text(query.strip())
        except ValueError:
            return []

        # Search vector store
        search_results = self.vector_store.search(
            query_embedding,
            top_k=top_k,
            filters=filters,
        )

        # Convert to RetrievalResult objects with full provenance
        results = []
        for rank, (chunk_id, metadata, similarity_score) in enumerate(search_results, start=1):
            result = RetrievalResult(
                chunk_id=metadata.get("chunk_id", ""),
                document_id=metadata.get("document_id", ""),
                source_id=metadata.get("source_id", ""),
                provision_id=metadata.get("provision_id", ""),
                provision_number=metadata.get("provision_number", ""),
                heading=metadata.get("heading", ""),
                text=metadata.get("text", ""),
                page_number=metadata.get("page_number"),
                source_locator=metadata.get("source_locator"),
                official_url=metadata.get("official_url", ""),
                version=metadata.get("version", "UNKNOWN"),
                status=metadata.get("status", "ACTIVE"),
                content_hash=metadata.get("content_hash", ""),
                similarity_score=similarity_score,
                rank=rank,
            )
            results.append(result)

        return results

    def search_from_document(
        self,
        document_id: str,
        query_text: str,
        top_k: int = 5,
        status_filter: Optional[List[str]] = None,
    ) -> List[RetrievalResult]:
        """
        Search using text extracted from a user document (tender).
        
        The document_id is for logging/tracking only.
        The query_text is embedded and searched against regulations.
        
        The user document is NOT added to regulatory authority.
        
        Args:
            document_id: ID of user's uploaded document (for context only).
            query_text: Extracted text to use as retrieval query.
            top_k: Number of results.
            status_filter: Filter by provision status.
            
        Returns:
            List of RetrievalResult objects.
        """
        # User document is QUERY, not regulatory authority
        # Simply search with the extracted text
        return self.search(query_text, top_k=top_k, status_filter=status_filter)

    def get_stats(self) -> Dict[str, Any]:
        """Get retrieval system statistics."""
        return {
            "indexed_chunks": self.vector_store.count(),
            "embedding_provider": self.embedding_provider.__class__.__name__,
            "embedding_dimension": self.embedding_provider.get_embedding_dimension(),
            "vector_store": self.vector_store.__class__.__name__,
            "max_chunk_size": self.chunking_strategy.max_chunk_size,
        }

    def clear_index(self) -> None:
        """Clear the vector index (for testing)."""
        self.vector_store.clear()


# Global retrieval service instance
_retrieval_service: Optional[RetrievalService] = None


def get_retrieval_service() -> RetrievalService:
    """Get or create global retrieval service instance."""
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = RetrievalService()
    return _retrieval_service


def set_retrieval_service(service: RetrievalService) -> None:
    """Set global retrieval service instance (for testing)."""
    global _retrieval_service
    _retrieval_service = service
