"""
Embedding provider abstraction for Phase 4.

Allows swappable embedding providers (local, cloud, LLM-based).
Keeps the application decoupled from any specific embedding vendor.

For MVP: Deterministic test embedding using text length/hash.
Future: OpenAI, Hugging Face, local models, etc.
"""

import hashlib
import os
from abc import ABC, abstractmethod
from typing import List, Optional


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.
    
    All providers must implement embed_text() and embed_batch().
    """

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text string.
        
        Args:
            text: Text to embed.
            
        Returns:
            Embedding vector as list of floats.
            
        Raises:
            ValueError: If text is empty.
            RuntimeError: If embedding fails.
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple text strings.
        
        Args:
            texts: List of texts to embed.
            
        Returns:
            List of embedding vectors.
            
        Raises:
            ValueError: If texts list is empty.
            RuntimeError: If embedding fails.
        """
        pass

    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """
        Return the dimension of embeddings from this provider.
        
        Used for vector store initialization and validation.
        """
        pass


class DeterministicTestEmbedding(EmbeddingProvider):
    """
    Deterministic test embedding using text hash and statistics.
    
    Properties:
    - Deterministic: Same text always produces same embedding.
    - Reproducible: Works offline without external dependencies.
    - Fast: Uses hash and text statistics.
    - Suitable for: Testing, evaluation, local development.
    
    NOT for production use.
    
    Embedding dimension: 384 (mimics common embedding sizes).
    """

    EMBEDDING_DIM = 384

    def embed_text(self, text: str) -> List[float]:
        """Create deterministic embedding from text."""
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text.")

        text = text.strip()

        # Create deterministic embedding using hash and text features
        embedding = self._hash_to_vector(text, self.EMBEDDING_DIM)
        return embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts."""
        if not texts:
            raise ValueError("Cannot embed empty batch.")

        embeddings = []
        for text in texts:
            try:
                embedding = self.embed_text(text)
                embeddings.append(embedding)
            except ValueError:
                # Skip empty texts in batch
                continue

        if not embeddings:
            raise ValueError("No valid texts to embed in batch.")

        return embeddings

    def get_embedding_dimension(self) -> int:
        """Return embedding dimension."""
        return self.EMBEDDING_DIM

    @staticmethod
    def _hash_to_vector(text: str, dim: int) -> List[float]:
        """
        Convert text to deterministic vector using hash.
        
        Strategy:
        1. Hash text with SHA256.
        2. Extract byte sequences.
        3. Normalize to range [-1, 1].
        4. Repeat/truncate to desired dimension.
        """
        hash_obj = hashlib.sha256(text.encode("utf-8"))
        hash_bytes = hash_obj.digest()

        # Convert bytes to floats in range [-1, 1]
        vector = []
        for i in range(dim):
            byte_index = i % len(hash_bytes)
            byte_val = hash_bytes[byte_index]
            # Normalize byte (0-255) to (-1, 1)
            normalized = (byte_val / 127.5) - 1.0
            vector.append(normalized)

        return vector


class OpenAIEmbedding(EmbeddingProvider):
    """
    OpenAI embedding provider (placeholder for future implementation).
    
    Requires:
    - OPENAI_API_KEY environment variable
    - openai Python package
    
    Reserved for a future semantic-embedding upgrade; not used by the
    current build (see README: "What is actually AI vs deterministic logic").
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        """
        Initialize OpenAI embedding provider.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var).
            model: Embedding model name.
            
        Raises:
            ValueError: If API key not provided and env var not set.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided and OPENAI_API_KEY not set.")

        self.model = model
        self._client = None  # Lazy load openai client

    def embed_text(self, text: str) -> List[float]:
        """NOT IMPLEMENTED for Phase 4 MVP."""
        raise NotImplementedError("OpenAI embedding not yet implemented. Use DeterministicTestEmbedding for Phase 4 MVP.")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """NOT IMPLEMENTED for Phase 4 MVP."""
        raise NotImplementedError("OpenAI embedding not yet implemented. Use DeterministicTestEmbedding for Phase 4 MVP.")

    def get_embedding_dimension(self) -> int:
        """OpenAI text-embedding-3-small returns 1536 dimensions."""
        return 1536


def get_embedding_provider(provider_name: str = "deterministic") -> EmbeddingProvider:
    """
    Factory function to get an embedding provider.
    
    Args:
        provider_name: Name of provider ("deterministic", "openai", etc.).
        
    Returns:
        EmbeddingProvider instance.
        
    Raises:
        ValueError: If provider name is unknown.
    """
    if provider_name == "deterministic":
        return DeterministicTestEmbedding()
    elif provider_name == "openai":
        return OpenAIEmbedding()
    else:
        raise ValueError(f"Unknown embedding provider: {provider_name}")
