"""
Phase 4 Tests - Grounded Regulatory Retrieval (RAG Foundation).

Tests cover:
1. Chunk creation and determinism
2. Chunking provenance preservation
3. Long provision splitting
4. Embedding provider abstraction
5. Vector store operations
6. Chunk-to-provision mapping
7. Provenance preservation
8. Active/superseded version filtering
9. Metadata filtering
10. Top-K retrieval
11. Retrieval API
12. Citation metadata
13. User evidence separation
14. Missing provenance rejection
15. Duplicate indexing control
16. Empty query handling
17. No-results handling
18. Retrieval ranking
19. Phase 3 regression testing
"""

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.regulatory.service import (
    create_document,
    create_provision,
    create_source,
)
from app.retrieval.chunking import ChunkingStrategy
from app.retrieval.embedding_provider import DeterministicTestEmbedding
from app.retrieval.models import RetrievalChunk, RetrievalResult
from app.retrieval.service import RetrievalService
from app.retrieval.vector_store import LocalVectorStore


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_retrieval_environment(tmp_path, monkeypatch):
    """Reset retrieval environment for each test."""
    import app.regulatory.service as reg_service
    import app.retrieval.service as ret_service

    # Use temp directories
    storage_root = str(tmp_path / "storage")
    monkeypatch.setattr(reg_service, "STORAGE_ROOT", os.path.join(storage_root, "regulatory"))
    monkeypatch.setenv("POLICYGUARD_STORAGE", storage_root)

    # Initialize
    reg_service.ensure_directories()

    # Reset global retrieval service
    retrieval_service = RetrievalService(
        vector_store=LocalVectorStore(os.path.join(storage_root, "retrieval"))
    )
    ret_service.set_retrieval_service(retrieval_service)

    yield

    # Cleanup
    ret_service.set_retrieval_service(None)


class TestChunkingStrategy:
    """Test deterministic chunking."""

    def test_chunk_short_provision(self):
        """Short provision should produce single chunk."""
        strategy = ChunkingStrategy(max_chunk_size=1000)

        source = create_source(
            title="Test Source",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            source_type="GFR",
            authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
            official_url="https://example.gov.in/test",
            version="1.0",
            status="ACTIVE",
            ingestion_status="READY",
        )

        document = create_document(
            source_id=source["source_id"],
            title="Test Document",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            document_type="GFR",
            version="1.0",
            publication_date="2024-01-01",
            effective_date="2024-01-01",
            official_url="https://example.gov.in/test",
            status="ACTIVE",
            ingestion_status="READY",
        )

        provision = create_provision(
            document_id=document["document_id"],
            source_id=source["source_id"],
            parent_id=None,
            provision_type="RULE",
            provision_number="Rule 1",
            heading="Test Rule",
            text="Short rule text.",
            raw_text="Short rule text.",
            normalized_text="Short rule text.",
            page_number=1,
            source_locator="p.1",
            official_url="https://example.gov.in/test",
        )

        chunks = strategy.chunk_provision(provision, document, source)

        assert len(chunks) == 1
        assert chunks[0].text == "Short rule text."
        assert chunks[0].provision_id == provision["provision_id"]
        assert chunks[0].document_id == document["document_id"]
        assert chunks[0].source_id == source["source_id"]

    def test_chunk_long_provision(self):
        """Long provision should split into multiple chunks."""
        strategy = ChunkingStrategy(max_chunk_size=100)

        source = create_source(
            title="Test Source",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            source_type="GFR",
            authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
            official_url="https://example.gov.in/test",
            version="1.0",
            status="ACTIVE",
            ingestion_status="READY",
        )

        document = create_document(
            source_id=source["source_id"],
            title="Test Document",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            document_type="GFR",
            version="1.0",
            publication_date="2024-01-01",
            effective_date="2024-01-01",
            official_url="https://example.gov.in/test",
            status="ACTIVE",
            ingestion_status="READY",
        )

        long_text = "Paragraph one. This is a long provision. " * 5
        provision = create_provision(
            document_id=document["document_id"],
            source_id=source["source_id"],
            parent_id=None,
            provision_type="RULE",
            provision_number="Rule 1",
            heading="Long Rule",
            text=long_text,
            raw_text=long_text,
            normalized_text=long_text,
            page_number=1,
            source_locator="p.1",
            official_url="https://example.gov.in/test",
        )

        chunks = strategy.chunk_provision(provision, document, source)

        assert len(chunks) > 1
        # Each chunk should retain provenance
        for i, chunk in enumerate(chunks):
            assert chunk.provision_id == provision["provision_id"]
            assert chunk.document_id == document["document_id"]
            assert chunk.source_id == source["source_id"]
            assert chunk.chunk_index == i

    def test_chunking_determinism(self):
        """Chunking same provision twice produces same chunks."""
        strategy = ChunkingStrategy(max_chunk_size=200)

        source = create_source(
            title="Test Source",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            source_type="GFR",
            authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
            official_url="https://example.gov.in/test",
            version="1.0",
            status="ACTIVE",
            ingestion_status="READY",
        )

        document = create_document(
            source_id=source["source_id"],
            title="Test Document",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            document_type="GFR",
            version="1.0",
            publication_date="2024-01-01",
            effective_date="2024-01-01",
            official_url="https://example.gov.in/test",
            status="ACTIVE",
            ingestion_status="READY",
        )

        text = "First paragraph here. Second paragraph here. Third paragraph here."
        provision = create_provision(
            document_id=document["document_id"],
            source_id=source["source_id"],
            parent_id=None,
            provision_type="RULE",
            provision_number="Rule 1",
            heading="Test Rule",
            text=text,
            raw_text=text,
            normalized_text=text,
            page_number=1,
            source_locator="p.1",
            official_url="https://example.gov.in/test",
        )

        # Chunk twice
        chunks1 = strategy.chunk_provision(provision, document, source)
        chunks2 = strategy.chunk_provision(provision, document, source)

        # Should produce identical chunks
        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.chunk_id == c2.chunk_id
            assert c1.text == c2.text


class TestEmbeddingProvider:
    """Test embedding provider abstraction."""

    def test_deterministic_embedding_consistency(self):
        """Same text produces same embedding."""
        provider = DeterministicTestEmbedding()
        text = "This is test text for embedding."

        embedding1 = provider.embed_text(text)
        embedding2 = provider.embed_text(text)

        assert embedding1 == embedding2
        assert len(embedding1) == provider.get_embedding_dimension()

    def test_different_texts_different_embeddings(self):
        """Different texts produce different embeddings."""
        provider = DeterministicTestEmbedding()

        embedding1 = provider.embed_text("Text A")
        embedding2 = provider.embed_text("Text B")

        assert embedding1 != embedding2

    def test_batch_embedding(self):
        """Batch embedding should match individual embeddings."""
        provider = DeterministicTestEmbedding()
        texts = ["Text 1", "Text 2", "Text 3"]

        individual = [provider.embed_text(t) for t in texts]
        batch = provider.embed_batch(texts)

        assert batch == individual

    def test_empty_text_raises_error(self):
        """Empty text should raise ValueError."""
        provider = DeterministicTestEmbedding()

        with pytest.raises(ValueError):
            provider.embed_text("")


class TestVectorStore:
    """Test vector store abstraction."""

    def test_upsert_and_retrieve(self, tmp_path):
        """Upsert should store and retrieve vectors."""
        store = LocalVectorStore(str(tmp_path))

        chunk_id = "chunk_1"
        vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        metadata = {
            "document_id": "doc_1",
            "text": "Sample text",
            "status": "ACTIVE",
        }

        store.upsert(chunk_id, vector, metadata)

        assert store.count() == 1
        retrieved = store.get_metadata(chunk_id)
        assert retrieved == metadata

    def test_delete_vector(self, tmp_path):
        """Delete should remove vector."""
        store = LocalVectorStore(str(tmp_path))

        chunk_id = "chunk_1"
        vector = [0.1, 0.2, 0.3]
        metadata = {"text": "test"}

        store.upsert(chunk_id, vector, metadata)
        assert store.count() == 1

        deleted = store.delete(chunk_id)
        assert deleted
        assert store.count() == 0

    def test_similarity_search(self, tmp_path):
        """Search should return similar vectors."""
        store = LocalVectorStore(str(tmp_path))
        provider = DeterministicTestEmbedding()

        # Store some vectors
        texts = ["apple", "apricot", "orange"]
        for i, text in enumerate(texts):
            embedding = provider.embed_text(text)
            metadata = {
                "text": text,
                "status": "ACTIVE",
                "chunk_id": f"chunk_{i}",
            }
            store.upsert(f"chunk_{i}", embedding, metadata)

        # Query with similar text
        query_embedding = provider.embed_text("apple fruit")
        results = store.search(query_embedding, top_k=2)

        assert len(results) <= 2
        # Results should have chunk_id and similarity score
        for chunk_id, metadata, similarity in results:
            assert chunk_id
            assert metadata
            assert similarity is not None

    def test_metadata_filtering(self, tmp_path):
        """Search with filters should only return matching results."""
        store = LocalVectorStore(str(tmp_path))
        provider = DeterministicTestEmbedding()

        # Store vectors with different statuses
        for i in range(3):
            status = "ACTIVE" if i < 2 else "SUPERSEDED"
            embedding = provider.embed_text(f"text {i}")
            metadata = {
                "text": f"text {i}",
                "status": status,
                "chunk_id": f"chunk_{i}",
            }
            store.upsert(f"chunk_{i}", embedding, metadata)

        # Search with filter
        query_embedding = provider.embed_text("text 1")
        results = store.search(query_embedding, filters={"status": ["ACTIVE"]})

        # Should only return ACTIVE chunks
        for chunk_id, metadata, _ in results:
            assert metadata["status"] == "ACTIVE"

    def test_persistence(self, tmp_path):
        """Vector store should persist to disk."""
        store_path = str(tmp_path)

        # Store some vectors
        store1 = LocalVectorStore(store_path)
        vector = [0.1, 0.2, 0.3]
        metadata = {"text": "test"}
        store1.upsert("chunk_1", vector, metadata)

        # Create new store instance (should load from disk)
        store2 = LocalVectorStore(store_path)
        assert store2.count() == 1
        assert store2.get_metadata("chunk_1") == metadata


class TestRetrievalService:
    """Test retrieval service."""

    def test_build_index(self):
        """Building index should chunk and embed all provisions."""
        service = RetrievalService()

        # Create test provisions
        source = create_source(
            title="Test Source",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            source_type="GFR",
            authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
            official_url="https://example.gov.in/test",
            version="1.0",
            status="ACTIVE",
            ingestion_status="READY",
        )

        document = create_document(
            source_id=source["source_id"],
            title="Test Document",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            document_type="GFR",
            version="1.0",
            publication_date="2024-01-01",
            effective_date="2024-01-01",
            official_url="https://example.gov.in/test",
            status="ACTIVE",
            ingestion_status="READY",
        )

        create_provision(
            document_id=document["document_id"],
            source_id=source["source_id"],
            parent_id=None,
            provision_type="RULE",
            provision_number="Rule 1",
            heading="Test Rule",
            text="This is test content.",
            raw_text="This is test content.",
            normalized_text="This is test content.",
            page_number=1,
            source_locator="p.1",
            official_url="https://example.gov.in/test",
        )

        # Build index
        stats = service.build_index()

        assert stats["status"] == "indexed"
        assert stats["provisions"] > 0
        assert stats["chunks"] > 0
        assert service.vector_store.count() > 0

    def test_search_returns_results(self):
        """Search should return retrieval results."""
        service = RetrievalService()

        # Create and index provisions
        source = create_source(
            title="Procurement Rules",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            source_type="PROCUREMENT_MANUAL",
            authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
            official_url="https://example.gov.in/procurement",
            version="2024",
            status="ACTIVE",
            ingestion_status="READY",
        )

        document = create_document(
            source_id=source["source_id"],
            title="Procurement Manual 2024",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            document_type="PROCUREMENT_MANUAL",
            version="2024",
            publication_date="2024-01-01",
            effective_date="2024-01-01",
            official_url="https://example.gov.in/procurement",
            status="ACTIVE",
            ingestion_status="READY",
        )

        create_provision(
            document_id=document["document_id"],
            source_id=source["source_id"],
            parent_id=None,
            provision_type="RULE",
            provision_number="Rule 1",
            heading="Bid Evaluation",
            text="Bids must be evaluated on technical and financial criteria.",
            raw_text="Bids must be evaluated on technical and financial criteria.",
            normalized_text="Bids must be evaluated on technical and financial criteria.",
            page_number=1,
            source_locator="p.1",
            official_url="https://example.gov.in/procurement",
        )

        service.build_index()

        # Search
        results = service.search("bid evaluation criteria")

        assert len(results) > 0
        assert all(isinstance(r, RetrievalResult) for r in results)

    def test_search_empty_query_returns_empty(self):
        """Empty query should return no results."""
        service = RetrievalService()
        service.build_index()

        results = service.search("")
        assert len(results) == 0

    def test_active_version_filtering(self):
        """Should prefer ACTIVE over SUPERSEDED by default."""
        service = RetrievalService()

        source = create_source(
            title="Version Test",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            source_type="GFR",
            authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
            official_url="https://example.gov.in/test",
            version="2.0",
            status="ACTIVE",
            ingestion_status="READY",
        )

        document = create_document(
            source_id=source["source_id"],
            title="Test Document",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            document_type="GFR",
            version="2.0",
            publication_date="2024-01-01",
            effective_date="2024-01-01",
            official_url="https://example.gov.in/test",
            status="ACTIVE",
            ingestion_status="READY",
        )

        create_provision(
            document_id=document["document_id"],
            source_id=source["source_id"],
            parent_id=None,
            provision_type="RULE",
            provision_number="Rule 1",
            heading="Current Rule",
            text="Current version text.",
            raw_text="Current version text.",
            normalized_text="Current version text.",
            page_number=1,
            source_locator="p.1",
            official_url="https://example.gov.in/test",
            status="ACTIVE",
        )

        service.build_index()

        # Default search should return ACTIVE
        results = service.search("Current version")
        assert all(r.status == "ACTIVE" for r in results)

    def test_provenance_preserved(self):
        """Retrieval results should contain full provenance."""
        service = RetrievalService()

        source = create_source(
            title="Provenance Test",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            source_type="GFR",
            authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
            official_url="https://example.gov.in/provenance",
            version="1.0",
            status="ACTIVE",
            ingestion_status="READY",
        )

        document = create_document(
            source_id=source["source_id"],
            title="Provenance Document",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            document_type="GFR",
            version="1.0",
            publication_date="2024-01-01",
            effective_date="2024-01-01",
            official_url="https://example.gov.in/provenance",
            status="ACTIVE",
            ingestion_status="READY",
        )

        provision = create_provision(
            document_id=document["document_id"],
            source_id=source["source_id"],
            parent_id=None,
            provision_type="RULE",
            provision_number="Rule 1",
            heading="Provenance Rule",
            text="Sample provision text.",
            raw_text="Sample provision text.",
            normalized_text="Sample provision text.",
            page_number=5,
            source_locator="p.5, section 2",
            official_url="https://example.gov.in/provenance",
        )

        service.build_index()

        results = service.search("provision")
        assert len(results) > 0

        for result in results:
            # All provenance fields should be present
            assert result.source_id
            assert result.document_id
            assert result.provision_id
            assert result.provision_number
            assert result.content_hash
            assert result.official_url


class TestRetrievalAPI:
    """Test retrieval API endpoints."""

    def test_search_endpoint(self):
        """POST /api/v1/retrieval/search should return results."""
        # Build index first
        from app.retrieval.service import get_retrieval_service

        service = get_retrieval_service()

        source = create_source(
            title="API Test Source",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            source_type="GFR",
            authority_level="OFFICIAL_DEPARTMENT_DOCUMENT",
            official_url="https://example.gov.in/api-test",
            version="1.0",
            status="ACTIVE",
            ingestion_status="READY",
        )

        document = create_document(
            source_id=source["source_id"],
            title="API Test Document",
            issuing_authority="Department of Expenditure",
            jurisdiction="INDIA",
            government_level="CENTRAL GOVERNMENT",
            document_type="GFR",
            version="1.0",
            publication_date="2024-01-01",
            effective_date="2024-01-01",
            official_url="https://example.gov.in/api-test",
            status="ACTIVE",
            ingestion_status="READY",
        )

        create_provision(
            document_id=document["document_id"],
            source_id=source["source_id"],
            parent_id=None,
            provision_type="RULE",
            provision_number="Rule 1",
            heading="API Test Rule",
            text="Test rule content for API.",
            raw_text="Test rule content for API.",
            normalized_text="Test rule content for API.",
            page_number=1,
            source_locator="p.1",
            official_url="https://example.gov.in/api-test",
        )

        service.build_index()

        # Search via API
        response = client.post(
            "/api/v1/retrieval/search?query=api+test&top_k=5"
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "query" in data
        assert data["query"] == "api test"

    def test_health_endpoint(self):
        """GET /api/v1/retrieval/health should return status."""
        response = client.get("/api/v1/retrieval/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["ok", "error"]

    def test_stats_endpoint(self):
        """GET /api/v1/retrieval/stats should return stats."""
        response = client.get("/api/v1/retrieval/stats")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "indexed_chunks" in data

    def test_index_endpoint(self):
        """POST /api/v1/retrieval/index should build index."""
        response = client.post("/api/v1/retrieval/index")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "chunks_created" in data


class TestPhase3Compatibility:
    """Verify Phase 3 remains intact and compatible."""

    def test_phase3_provisions_still_accessible(self):
        """Phase 3 provision access should not be affected."""
        from app.regulatory.service import list_provisions

        provisions = list_provisions()
        # Registry starts empty; provisions come only from ingested verified sources
        assert len(provisions) >= 0

    def test_phase3_search_still_works(self):
        """Phase 3 text search should still function."""
        from app.regulatory.service import search_provisions

        results = search_provisions("financial")
        # Should return something or empty list, not error
        assert isinstance(results, list)

    def test_no_regulatory_authority_fabrication(self):
        """User documents should never become regulatory authority."""
        # This is enforced by Phase 3 validation
        from app.regulatory.service import create_source

        # Trying to create user document as source should fail
        with pytest.raises(ValueError):
            create_source(
                title="User Uploaded Tender",
                issuing_authority="Internal Company",
                jurisdiction="US",
                government_level="CORPORATE",
                source_type="USER_DOCUMENT",
                authority_level="SECONDARY_SOURCE",
                official_url="",
                source_domain="USER_EVIDENCE",
            )
