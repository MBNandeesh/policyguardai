"""
Vector store abstraction and local in-memory implementation for Phase 4.

Abstracts vector storage to allow future replacement with production databases
(Qdrant, pgvector, FAISS, etc.) without changing application code.

MVP implementation: In-memory JSON-based store with deterministic persistence.
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class VectorStore(ABC):
    """
    Abstract base class for vector storage.
    
    Maintains mapping: vector -> chunk_id -> provision_id -> document_id -> source_id
    Every vector result must be traceable to authoritative provenance.
    """

    @abstractmethod
    def upsert(
        self,
        chunk_id: str,
        vector: List[float],
        metadata: Dict[str, Any],
    ) -> None:
        """
        Insert or update a vector.
        
        Args:
            chunk_id: Unique identifier for the chunk.
            vector: Embedding vector.
            metadata: Chunk metadata (provenance, text, etc.).
        """
        pass

    @abstractmethod
    def delete(self, chunk_id: str) -> bool:
        """
        Delete a vector by chunk ID.
        
        Returns True if deleted, False if not found.
        """
        pass

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding.
            top_k: Number of results.
            filters: Metadata filters (e.g., {"status": "ACTIVE"}).
            
        Returns:
            List of (chunk_id, metadata, similarity_score) tuples, sorted by score descending.
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """Return total number of vectors in store."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Delete all vectors from store."""
        pass

    @abstractmethod
    def get_metadata(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a chunk without searching."""
        pass


class LocalVectorStore(VectorStore):
    """
    Local in-memory vector store with JSON persistence.
    
    Properties:
    - In-memory index for fast search.
    - JSON persistence to disk.
    - Deterministic for testing.
    - No external dependencies.
    - Suitable for MVP and local development.
    
    Similarity measure: Cosine similarity (standard for embeddings).
    
    Storage format:
    {
      "vectors": {
        "chunk_id": {
          "vector": [...],
          "metadata": {...},
          "created_at": "...",
          "updated_at": "..."
        }
      }
    }
    """

    def __init__(self, storage_path: str = ""):
        """
        Initialize local vector store.
        
        Args:
            storage_path: Path to store vector index JSON file.
                         Defaults to regulatory storage root.
        """
        from app.config import settings

        if not storage_path:
            storage_path = os.path.join(settings.storage_path, "retrieval")

        self.storage_path = storage_path
        self.index_file = os.path.join(storage_path, "vector_index.json")

        # Ensure storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)

        # In-memory index
        self._vectors: Dict[str, Dict[str, Any]] = {}

        # Load from disk if exists
        self._load()

    def upsert(
        self,
        chunk_id: str,
        vector: List[float],
        metadata: Dict[str, Any],
    ) -> None:
        """Insert or update a vector with metadata."""
        import datetime

        if not chunk_id:
            raise ValueError("chunk_id cannot be empty.")
        if not vector:
            raise ValueError("vector cannot be empty.")
        if not metadata:
            raise ValueError("metadata cannot be empty.")

        now = datetime.datetime.utcnow().isoformat() + "Z"

        self._vectors[chunk_id] = {
            "vector": vector,
            "metadata": metadata,
            "created_at": self._vectors.get(chunk_id, {}).get("created_at", now),
            "updated_at": now,
        }

        self._save()

    def delete(self, chunk_id: str) -> bool:
        """Delete a vector by chunk ID."""
        if chunk_id in self._vectors:
            del self._vectors[chunk_id]
            self._save()
            return True
        return False

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Search for similar vectors using cosine similarity.
        
        Optionally filter by metadata (status, jurisdiction, etc.).
        """
        if not query_vector:
            raise ValueError("query_vector cannot be empty.")
        if top_k <= 0:
            raise ValueError("top_k must be positive.")

        filters = filters or {}

        # Calculate similarities
        similarities = []
        for chunk_id, data in self._vectors.items():
            # Apply metadata filters
            metadata = data.get("metadata", {})
            if not self._matches_filters(metadata, filters):
                continue

            vector = data.get("vector", [])
            if not vector:
                continue

            # Cosine similarity
            similarity = self._cosine_similarity(query_vector, vector)
            similarities.append((chunk_id, metadata, similarity))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[2], reverse=True)

        # Return top-k
        return similarities[:top_k]

    def count(self) -> int:
        """Return total number of vectors."""
        return len(self._vectors)

    def clear(self) -> None:
        """Delete all vectors."""
        self._vectors.clear()
        self._save()

    def get_metadata(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a chunk."""
        if chunk_id in self._vectors:
            return self._vectors[chunk_id].get("metadata")
        return None

    def _matches_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if metadata matches all filters."""
        for key, value in filters.items():
            if isinstance(value, list):
                # Filter is a list of acceptable values
                if metadata.get(key) not in value:
                    return False
            else:
                # Filter is a single value
                if metadata.get(key) != value:
                    return False
        return True

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = (sum(a * a for a in vec1) ** 0.5)
        magnitude2 = (sum(b * b for b in vec2) ** 0.5)

        if magnitude1 == 0.0 or magnitude2 == 0.0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def _save(self) -> None:
        """Persist vector index to disk."""
        os.makedirs(self.storage_path, exist_ok=True)

        payload = {
            "vectors": self._vectors,
            "metadata": {
                "total_vectors": len(self._vectors),
                "updated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            },
        }

        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    def _load(self) -> None:
        """Load vector index from disk."""
        if not os.path.exists(self.index_file):
            return

        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
                self._vectors = payload.get("vectors", {})
        except (json.JSONDecodeError, IOError):
            # If file is corrupted, start fresh
            self._vectors = {}


def get_vector_store(store_type: str = "local", storage_path: str = "") -> VectorStore:
    """
    Factory function to get a vector store.
    
    Args:
        store_type: Type of store ("local", "qdrant", etc.).
        storage_path: Storage path for local store.
        
    Returns:
        VectorStore instance.
        
    Raises:
        ValueError: If store type is unknown.
    """
    if store_type == "local":
        return LocalVectorStore(storage_path)
    else:
        raise ValueError(f"Unknown vector store type: {store_type}")
