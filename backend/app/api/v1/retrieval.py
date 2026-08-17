"""
Retrieval API endpoints for Phase 4.

Provides REST API for regulatory retrieval and indexing.

Endpoints:
- POST /api/v1/retrieval/search - Semantic retrieval
- GET /api/v1/retrieval/health - Health check
- GET /api/v1/retrieval/stats - Retrieval statistics
- POST /api/v1/retrieval/index - Build/rebuild index
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from app.retrieval.service import get_retrieval_service

router = APIRouter()


class SearchRequest:
    """Search request model."""

    def __init__(
        self,
        query: str,
        top_k: int = 5,
        status_filter: Optional[List[str]] = None,
        jurisdiction_filter: Optional[List[str]] = None,
        source_type_filter: Optional[List[str]] = None,
    ):
        self.query = query
        self.top_k = top_k
        self.status_filter = status_filter or ["ACTIVE"]
        self.jurisdiction_filter = jurisdiction_filter
        self.source_type_filter = source_type_filter


class SearchResponse:
    """Search response model."""

    def __init__(
        self,
        results: List[Dict[str, Any]],
        query: str,
        total: int,
        returned: int,
    ):
        self.results = results
        self.query = query
        self.total = total
        self.returned = returned

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            "results": self.results,
            "query": self.query,
            "total": self.total,
            "returned": self.returned,
        }


@router.post("/retrieval/search")
async def search(
    query: str,
    top_k: int = 5,
    status_filter: Optional[List[str]] = None,
    jurisdiction_filter: Optional[List[str]] = None,
    source_type_filter: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Search for relevant regulatory provisions.
    
    Args:
        query: Search query text (required).
        top_k: Number of results (default 5).
        status_filter: Filter by provision status (default ["ACTIVE"]).
        jurisdiction_filter: Filter by jurisdiction.
        source_type_filter: Filter by source type.
        
    Returns:
        List of retrieval results with provenance.
        
    NOTE: This endpoint performs semantic search. It does NOT generate compliance verdicts.
    Results are regulations retrieved from the knowledge base, not legal conclusions.
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="query parameter is required")

    if top_k <= 0 or top_k > 100:
        raise HTTPException(status_code=400, detail="top_k must be between 1 and 100")

    try:
        retrieval_service = get_retrieval_service()

        # If vector index is empty, try to build it
        if retrieval_service.vector_store.count() == 0:
            retrieval_service.build_index()

        # Search
        results = retrieval_service.search(
            query=query.strip(),
            top_k=top_k,
            status_filter=status_filter or ["ACTIVE"],
            jurisdiction_filter=jurisdiction_filter,
            source_type_filter=source_type_filter,
        )

        # Convert results to dictionaries
        result_dicts = [result.to_dict() for result in results]

        return SearchResponse(
            results=result_dicts,
            query=query,
            total=len(results),
            returned=len(results),
        ).to_dict()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval search failed: {str(e)}")


@router.get("/retrieval/health")
async def health() -> Dict[str, str]:
    """
    Health check for retrieval system.
    
    Returns:
        Health status and indexed chunk count.
    """
    try:
        retrieval_service = get_retrieval_service()
        chunk_count = retrieval_service.vector_store.count()

        status = "ok" if chunk_count >= 0 else "error"

        return {
            "status": status,
            "indexed_chunks": str(chunk_count),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@router.get("/retrieval/stats")
async def stats() -> Dict[str, Any]:
    """
    Get retrieval system statistics.
    
    Returns:
        System configuration and indexing stats.
    """
    try:
        retrieval_service = get_retrieval_service()
        stats_dict = retrieval_service.get_stats()

        return {
            "status": "ok",
            **stats_dict,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/retrieval/index")
async def index() -> Dict[str, Any]:
    """
    Build/rebuild the retrieval index from all regulatory provisions.
    
    Process:
    1. Load all provisions from Phase 3 regulatory database.
    2. Chunk each provision deterministically.
    3. Embed each chunk.
    4. Store in vector database.
    
    WARNING: This operation loads ALL provisions. For large knowledge bases,
    consider incremental indexing (future Phase).
    
    Returns:
        Indexing statistics.
        
    NOTE: Only regulatory authority provisions are indexed.
    User documents are never promoted to regulatory authority.
    """
    try:
        retrieval_service = get_retrieval_service()

        # Clear existing index
        retrieval_service.clear_index()

        # Build new index
        stats = retrieval_service.build_index()

        return {
            "status": stats.get("status", "unknown"),
            "provisions_indexed": stats.get("provisions", 0),
            "chunks_created": stats.get("chunks", 0),
            "chunks_embedded": stats.get("embedded", 0),
            "chunks_stored": stats.get("stored", 0),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")
