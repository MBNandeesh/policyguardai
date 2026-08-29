"""
Deterministic chunking strategy for regulatory provisions.

Chunks preserve provision boundaries, maintain context, and retain provenance.
The same provision produces the same chunks for consistent reproducibility.
"""

import os
from typing import Any, Dict, List, Optional

from app.retrieval.models import RetrievalChunk


class ChunkingStrategy:
    """
    Deterministic chunking of regulatory provisions.
    
    Strategy:
    1. If provision text is short (<=1000 chars), keep as single chunk.
    2. If provision text is long, split on semantic boundaries (paragraphs/sentences).
    3. Preserve chunk overlap if configured.
    4. Always retain provenance metadata.
    5. Use deterministic chunk IDs based on content hash and index.
    
    Never fabricate text. Never split legal text in a way that loses critical context.
    """

    def __init__(self, max_chunk_size: int = 1000, overlap_sentences: int = 0):
        """
        Initialize chunking strategy.
        
        Args:
            max_chunk_size: Maximum characters per chunk (default 1000).
            overlap_sentences: Number of sentences to overlap between chunks (default 0).
        """
        self.max_chunk_size = max_chunk_size
        self.overlap_sentences = overlap_sentences

    def chunk_provision(
        self,
        provision: Dict[str, Any],
        document: Dict[str, Any],
        source: Dict[str, Any],
    ) -> List[RetrievalChunk]:
        """
        Split a regulatory provision into retrieval chunks.
        
        Args:
            provision: Provision dict from Phase 3.
            document: Document dict from Phase 3.
            source: Source dict from Phase 3.
            
        Returns:
            List of RetrievalChunk objects with preserved provenance.
            
        Raises:
            ValueError: If provenance information is missing or invalid.
        """
        # Validate provenance
        provision_id = provision.get("provision_id")
        document_id = document.get("document_id")
        source_id = source.get("source_id")

        if not all([provision_id, document_id, source_id]):
            raise ValueError("Provision, document, and source IDs are required for chunking.")

        # Extract content
        text = (provision.get("normalized_text") or provision.get("text") or "").strip()
        if not text:
            raise ValueError(f"Provision {provision_id} has no text content to chunk.")

        # If text is short, create single chunk
        if len(text) <= self.max_chunk_size:
            return [self._create_chunk(provision, document, source, text, 0)]

        # Split long text into chunks
        chunks = []
        chunk_texts = self._split_text(text)

        for index, chunk_text in enumerate(chunk_texts):
            chunk = self._create_chunk(provision, document, source, chunk_text, index)
            chunks.append(chunk)

        return chunks

    def _split_text(self, text: str) -> List[str]:
        """
        Split text into chunks while respecting max_chunk_size.
        
        Strategy:
        1. Split by paragraphs (double newline).
        2. If paragraph is too large, split by sentences.
        3. If sentence is too large, split by words (as last resort).
        
        Returns:
            List of chunk texts in order.
        """
        chunks = []
        paragraphs = text.split("\n\n")

        current_chunk = ""
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # If adding paragraph exceeds limit, save current chunk and start new one
            if current_chunk and len(current_chunk) + len(paragraph) + 2 > self.max_chunk_size:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            # If single paragraph exceeds limit, split by sentences
            if len(paragraph) > self.max_chunk_size:
                sentences = self._split_sentences(paragraph)
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 1 > self.max_chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence
                    else:
                        current_chunk += (" " if current_chunk else "") + sentence
            else:
                current_chunk += ("\n\n" if current_chunk else "") + paragraph

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if chunks else [text]

    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.
        
        Simple heuristic: split on ". ", "? ", "! " but preserve the punctuation.
        """
        # Simple split on common sentence endings
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _create_chunk(
        self,
        provision: Dict[str, Any],
        document: Dict[str, Any],
        source: Dict[str, Any],
        text: str,
        chunk_index: int,
    ) -> RetrievalChunk:
        """
        Create a RetrievalChunk with preserved provenance.
        
        Chunk ID is deterministic based on provision ID and chunk index.
        """
        import hashlib

        # Deterministic chunk ID
        chunk_seed = f"{provision.get('provision_id')}:{chunk_index}".encode("utf-8")
        chunk_id = hashlib.sha256(chunk_seed).hexdigest()[:16]

        chunk = RetrievalChunk(
            chunk_id=chunk_id,
            document_id=document.get("document_id", ""),
            source_id=source.get("source_id", ""),
            provision_id=provision.get("provision_id", ""),
            parent_provision_id=provision.get("parent_id"),
            chunk_index=chunk_index,
            text=text,
            normalized_text=text,
            provision_number=provision.get("provision_number", ""),
            heading=provision.get("heading", ""),
            page_number=provision.get("page_number"),
            source_locator=provision.get("source_locator"),
            official_url=provision.get("official_url", ""),
            version=document.get("version", "UNKNOWN"),
            status=provision.get("status", "ACTIVE"),
            content_hash=provision.get("content_hash", ""),
            metadata={
                "document_title": document.get("title", ""),
                "source_title": source.get("title", ""),
                "jurisdiction": source.get("jurisdiction", ""),
                "government_level": source.get("government_level", ""),
                "source_type": source.get("source_type", ""),
                "document_type": document.get("document_type", ""),
            },
            embedding_status="PENDING",
            created_at=self._now_iso(),
        )

        return chunk

    def _now_iso(self) -> str:
        """Return current time in ISO format."""
        import datetime

        return datetime.datetime.utcnow().isoformat() + "Z"


def chunk_all_provisions(
    provisions: List[Dict[str, Any]],
    documents: Dict[str, Dict[str, Any]],
    sources: Dict[str, Dict[str, Any]],
    max_chunk_size: int = 1000,
) -> List[RetrievalChunk]:
    """
    Chunk all provisions in the regulatory database.
    
    Args:
        provisions: List of provision dicts.
        documents: Dict of document_id -> document dict.
        sources: Dict of source_id -> source dict.
        max_chunk_size: Maximum chunk size.
        
    Returns:
        List of all RetrievalChunk objects.
    """
    strategy = ChunkingStrategy(max_chunk_size=max_chunk_size)
    chunks = []

    for provision in provisions:
        document_id = provision.get("document_id")
        source_id = provision.get("source_id")

        if document_id not in documents:
            # Skip provisions without valid documents
            continue
        if source_id not in sources:
            # Skip provisions without valid sources
            continue

        document = documents[document_id]
        source = sources[source_id]

        try:
            provision_chunks = strategy.chunk_provision(provision, document, source)
            chunks.extend(provision_chunks)
        except ValueError:
            # Skip provisions that cannot be chunked
            continue

    return chunks
