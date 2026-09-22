# PolicyGuard AI - Phase 4: Grounded Regulatory Retrieval (RAG Foundation)

## Overview

Phase 4 implements the retrieval foundation for PolicyGuard AI's RAG (Retrieval-Augmented Generation) pipeline. This phase provides semantic search and retrieval capabilities while maintaining strict separation between regulatory authority and user evidence.

**IMPORTANT**: Phase 4 is **NOT** a compliance analysis system. It retrieves regulations only. Compliance verdicts belong to Phase 5+.

## Architecture

### High-Level Flow

```
USER TENDER / DOCUMENT
        ↓
PHASE 2 DOCUMENT EXTRACTION
        ↓
EXTRACTED TEXT (QUERY)
        ↓
PHASE 4 RETRIEVAL
        ↓
REGULATORY KNOWLEDGE BASE
        ↓
CHUNKS + EMBEDDINGS
        ↓
VECTOR SIMILARITY SEARCH
        ↓
TOP-K RELEVANT PROVISIONS
        ↓
CITATIONS + PROVENANCE
        ↓
[Phase 5+: Compliance Analysis]
```

### Core Components

#### 1. Chunking Strategy (`app/retrieval/chunking.py`)

**Purpose**: Convert regulatory provisions into retrieval-ready chunks while preserving provenance.

**Key Features**:
- Deterministic chunking (same input → same chunks)
- Respects provision boundaries where possible
- Smart splitting (paragraphs → sentences → words)
- Configurable chunk size (default 1000 chars)
- Preserves all provenance metadata

**Process**:
1. If provision ≤ max_chunk_size: create single chunk
2. If provision > max_chunk_size: split on semantic boundaries
3. Each chunk retains: provision_id, document_id, source_id, page, heading, etc.

**Example**:
```python
from app.retrieval.chunking import ChunkingStrategy

strategy = ChunkingStrategy(max_chunk_size=1000)
chunks = strategy.chunk_provision(provision, document, source)

# Result: List[RetrievalChunk] with preserved provenance
```

#### 2. Embedding Provider (`app/retrieval/embedding_provider.py`)

**Purpose**: Abstract embedding service to support multiple providers.

**Architecture**:
```
EmbeddingProvider (ABC)
    ├── DeterministicTestEmbedding
    │   └── Used for Phase 4 MVP (no external deps)
    └── OpenAIEmbedding
        └── Future: Cloud embeddings
```

**MVP Implementation** (DeterministicTestEmbedding):
- Deterministic (SHA256-based)
- Fast (no network)
- Reproducible (for testing)
- 384-dimensional embeddings
- Same text always produces same embedding

**Future Providers**:
- OpenAI text-embedding-3-small
- Local models (Sentence Transformers)
- Hugging Face
- Custom enterprise embeddings

**Swapping Providers**:
```python
# Use test embeddings
service = RetrievalService(
    embedding_provider=get_embedding_provider("deterministic")
)

# Use OpenAI (future)
service = RetrievalService(
    embedding_provider=get_embedding_provider("openai")
)
```

#### 3. Vector Store (`app/retrieval/vector_store.py`)

**Purpose**: Store, index, and search embeddings with metadata.

**Architecture**:
```
VectorStore (ABC)
    └── LocalVectorStore
        └── In-memory JSON-based
        └── Persisted to disk
        └── Suitable for MVP/dev
```

**Methods**:
- `upsert(chunk_id, vector, metadata)` - Insert/update
- `delete(chunk_id)` - Remove
- `search(query_vector, top_k, filters)` - Semantic search
- `count()` - Get index size
- `clear()` - Clear index
- `get_metadata(chunk_id)` - Retrieve metadata

**Metadata Filters**:
```python
# Filter by status
results = store.search(query_vec, filters={"status": ["ACTIVE"]})

# Filter by jurisdiction
results = store.search(query_vec, filters={"jurisdiction": ["INDIA"]})

# Combine filters
results = store.search(
    query_vec,
    filters={
        "status": ["ACTIVE"],
        "jurisdiction": ["INDIA"],
        "source_type": ["PROCUREMENT_MANUAL"]
    }
)
```

**Persistence**:
- Stored in `{STORAGE_ROOT}/retrieval/vector_index.json`
- Deterministic format (reproducible)
- Survives application restarts
- Can be backed up/restored

**Future Databases**:
- Qdrant
- pgvector (PostgreSQL)
- FAISS
- Weaviate

#### 4. Retrieval Service (`app/retrieval/service.py`)

**Purpose**: Orchestrate chunking, embedding, indexing, and search.

**Key Operations**:

**Build Index**:
```python
service = RetrievalService()
stats = service.build_index()

# Returns: {
#   "status": "indexed",
#   "provisions": 45,
#   "chunks": 87,
#   "embedded": 87,
#   "stored": 87
# }
```

**Search**:
```python
results = service.search(
    query="bid evaluation criteria",
    top_k=5,
    status_filter=["ACTIVE"],  # Default
    jurisdiction_filter=["INDIA"]
)

# Returns: List[RetrievalResult] with provenance
```

**Search from User Document**:
```python
# User tender is extracted and used as QUERY
# NOT added to regulatory authority
results = service.search_from_document(
    document_id="uploaded_tender_123",
    query_text="tender requirements...",
    top_k=5
)
```

**Get Statistics**:
```python
stats = service.get_stats()
# {
#   "indexed_chunks": 87,
#   "embedding_provider": "DeterministicTestEmbedding",
#   "embedding_dimension": 384,
#   "vector_store": "LocalVectorStore",
#   "max_chunk_size": 1000
# }
```

#### 5. Retrieval API (`app/api/v1/retrieval.py`)

**Endpoints**:

**POST /api/v1/retrieval/search**
```bash
curl -X POST "http://localhost:8000/api/v1/retrieval/search?query=procurement&top_k=5"

Response:
{
  "results": [
    {
      "chunk_id": "abc123...",
      "document_id": "doc_456",
      "source_id": "src_789",
      "provision_id": "prov_012",
      "provision_number": "Rule 5.2",
      "heading": "Bid Evaluation",
      "text": "Bids shall be evaluated on technical and financial criteria...",
      "page_number": 12,
      "source_locator": "p.12, section 5",
      "official_url": "https://example.gov.in/procurement",
      "version": "2024",
      "status": "ACTIVE",
      "similarity_score": 0.87,
      "rank": 1
    },
    ...
  ],
  "query": "procurement",
  "total": 5,
  "returned": 5
}
```

**GET /api/v1/retrieval/health**
```bash
curl http://localhost:8000/api/v1/retrieval/health

Response:
{
  "status": "ok",
  "indexed_chunks": "87"
}
```

**GET /api/v1/retrieval/stats**
```bash
curl http://localhost:8000/api/v1/retrieval/stats

Response:
{
  "status": "ok",
  "indexed_chunks": 87,
  "embedding_provider": "DeterministicTestEmbedding",
  "embedding_dimension": 384,
  "vector_store": "LocalVectorStore",
  "max_chunk_size": 1000
}
```

**POST /api/v1/retrieval/index**
```bash
curl -X POST http://localhost:8000/api/v1/retrieval/index

Response:
{
  "status": "indexed",
  "provisions_indexed": 45,
  "chunks_created": 87,
  "chunks_embedded": 87,
  "chunks_stored": 87
}
```

## Models

### RetrievalChunk
Represents a retrieval-ready chunk with full provenance.

Fields:
- `chunk_id` - Deterministic hash of provision_id:index
- `document_id` - Reference to regulatory document
- `source_id` - Reference to authoritative source
- `provision_id` - Reference to original provision (immutable)
- `chunk_index` - Position within provision chunks
- `text` - Chunk content
- `normalized_text` - Normalized version
- `provision_number` - Rule/section number
- `heading` - Original heading
- `page_number` - Page reference
- `source_locator` - Source-specific locator
- `official_url` - Authoritative URL
- `version` - Regulatory version
- `status` - ACTIVE/SUPERSEDED/etc
- `content_hash` - SHA256 of original provision
- `metadata` - Additional provenance
- `embedding_status` - PENDING/EMBEDDED/ERROR
- `vector` - Optional embedding

### RetrievalResult
Result of a retrieval query with ranking.

Fields:
- `chunk_id`, `document_id`, `source_id`, `provision_id` - Provenance
- `provision_number`, `heading`, `text` - Content
- `page_number`, `source_locator`, `official_url` - Citation info
- `version`, `status`, `content_hash` - Metadata
- `similarity_score` - Embedding similarity (0-1)
- `rank` - Result rank (1-indexed)

**Citation Metadata**:
```python
result.citation_metadata()
# Returns dict suitable for academic/legal citations
```

## Search Semantics

### Default Behavior
```python
# Retrieves only ACTIVE provisions from INDIA, CENTRAL GOVERNMENT
results = service.search("procurement")
```

### Filtering
```python
# Include superseded versions
results = service.search(
    "procurement",
    status_filter=["ACTIVE", "SUPERSEDED"]
)

# Filter by jurisdiction
results = service.search(
    "procurement",
    jurisdiction_filter=["INDIA", "KERALA"]
)

# Filter by source type
results = service.search(
    "procurement",
    source_type_filter=["GFR", "PROCUREMENT_MANUAL"]
)
```

### Version Safety (CRITICAL)
- Default search returns ACTIVE provisions only
- SUPERSEDED and ACTIVE results are **never mixed** unless explicitly requested
- Historical research requires explicit `status_filter` parameter

## Trust Boundaries

### REGULATORY AUTHORITY (Trustworthy)
- Phase 3 regulatory provisions
- Official government documents
- Verified authoritative sources
- Protected by Phase 3 validation

### USER EVIDENCE (Query Only)
- Uploaded tender documents
- Procurement notices
- Company policies
- Used as retrieval QUERY, never added to regulations

### Never Happens
```python
# ❌ INVALID: User document becomes regulatory source
user_tender → create_source() → REGULATORY_AUTHORITY

# ✅ VALID: User document is extracted and searched
user_tender → extract_text() → search_query() → regulations
```

## Hallucination Prevention

Phase 4 **never fabricates**:
- Rule numbers
- Legal text
- URLs
- Dates
- Authorities
- Citations

If evidence is missing:
```python
results = service.search(query)
if not results:
    return {"status": "NO_RESULT", "message": "No matching provisions found"}
```

## Determinism Guarantees

### Chunking
- Same provision → same chunks
- Same order, same IDs
- Reproducible across runs

### Embeddings
- Deterministic provider: same text → same embedding
- No randomness in MVP
- Enables testing without external services

### Search
- Same query + same index → same results
- Consistent ranking (cosine similarity)
- Reproducible for evaluation

## Testing

Phase 4 includes 24 comprehensive tests:

**Chunking Tests**:
- Short provision (1 chunk)
- Long provision (multiple chunks)
- Determinism (same input → same output)

**Embedding Tests**:
- Text consistency
- Batch processing
- Dimension validation

**Vector Store Tests**:
- Upsert/delete operations
- Cosine similarity search
- Metadata filtering
- Disk persistence

**Retrieval Service Tests**:
- Index building
- Search functionality
- Status filtering
- Provenance preservation

**API Tests**:
- /retrieval/search endpoint
- /retrieval/health endpoint
- /retrieval/stats endpoint
- /retrieval/index endpoint

**Phase 3 Compatibility**:
- All Phase 3 tests still pass
- No regulatory authority fabrication
- User evidence remains separate

## Configuration

### Environment Variables
```bash
# Not required for Phase 4 MVP
# OPENAI_API_KEY=...  # For future OpenAI provider
# EMBEDDING_PROVIDER=deterministic  # Default
# VECTOR_STORE_TYPE=local  # Default
```

### Chunk Size
```python
service = RetrievalService(max_chunk_size=1500)  # Custom size
```

### Custom Providers
```python
from app.retrieval.embedding_provider import EmbeddingProvider
from app.retrieval.vector_store import VectorStore

class CustomEmbedding(EmbeddingProvider):
    def embed_text(self, text: str) -> List[float]:
        # Custom implementation
        pass

class CustomVectorStore(VectorStore):
    def upsert(self, chunk_id, vector, metadata):
        # Custom implementation
        pass

service = RetrievalService(
    embedding_provider=CustomEmbedding(),
    vector_store=CustomVectorStore()
)
```

## Limitations (Phase 4 MVP)

### Intentional Scoping
- No compliance analysis
- No violation detection
- No recommendations
- No legal conclusions
- No LLM reasoning

### Known Limitations
- Local in-memory vector store (not production-scale)
- Deterministic embeddings (not semantic similarity to external models)
- No incremental indexing (rebuild entire index)
- No hybrid search (only vector similarity + filtering)
- No caching

### Roadmap (Phase 5+)
- Compliance reasoning
- Violation detection
- Scoring algorithms
- Report generation
- Production vector databases
- LLM integration
- Incremental indexing
- Hybrid search

## Files Created

```
backend/app/retrieval/
├── __init__.py                  # Module init
├── models.py                    # RetrievalChunk, RetrievalResult
├── chunking.py                  # ChunkingStrategy
├── embedding_provider.py        # EmbeddingProvider ABC + implementations
├── vector_store.py              # VectorStore ABC + LocalVectorStore
└── service.py                   # RetrievalService (orchestrator)

backend/app/api/v1/
└── retrieval.py                 # REST API endpoints

backend/tests/
└── test_retrieval_phase4.py     # 24 comprehensive tests

docs/
└── PHASE4.md                    # This file
```

## Files Modified

```
backend/app/main.py             # Added retrieval router
```

## Test Results

```
47 passed total:
- 23 Phase 1-3 tests (unchanged)
- 24 Phase 4 tests (new)

Exit code: 0
```

## Running Phase 4

**Build Index**:
```bash
curl -X POST http://localhost:8000/api/v1/retrieval/index
```

**Search**:
```bash
curl "http://localhost:8000/api/v1/retrieval/search?query=procurement"
```

**Check Stats**:
```bash
curl http://localhost:8000/api/v1/retrieval/stats
```

**Run Tests**:
```bash
pytest backend/tests/test_retrieval_phase4.py -v
pytest -q  # All tests
```

## Compliance

✅ Phase 4 Requirements:
- [x] Regulatory chunking
- [x] Retrieval-ready records with provenance
- [x] Embeddings abstraction
- [x] Vector storage abstraction
- [x] Deterministic metadata filtering
- [x] Semantic retrieval
- [x] Top-K retrieval
- [x] Provenance preservation
- [x] Citation-ready results
- [x] Retrieval API
- [x] Retrieval tests
- [x] Evaluation fixtures
- [x] Phase 3 compatibility (all tests pass)
- [x] No fabricated regulatory content
- [x] No compliance verdicts
- [x] No LLM reasoning
- [x] No hallucinations

❌ Phase 4 Non-Goals (Phase 5+):
- Legal conclusions
- Compliance scoring
- Violation detection
- Recommendations
- Automatic decisions

## Next Steps (Phase 5)

Phase 4 provides the foundation for Phase 5 (Compliance Analysis):
1. Retrieval results → Legal reasoning engine
2. Extracted evidence → Compliance checking
3. Violations → Scoring & reporting
4. Results → User-facing compliance report

Phase 4 is **COMPLETE** and **FROZEN** until Phase 5 requirements clarified.
