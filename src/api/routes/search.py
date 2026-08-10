from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from src.services.algolia_search import algolia_search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=Dict[str, Any])
async def search_endpoint(
    q: str = Query(..., min_length=1, description="Search query string"),
    entity_type: Optional[str] = Query(None, description="Optional entity filter: dataset, rule, alert, audit"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
) -> Dict[str, Any]:
    try:
        hits = algolia_search_service.search(query=q, entity_type=entity_type, limit=limit)
        return {
            "status": "success",
            "query": q,
            "entity_type": entity_type,
            "count": len(hits),
            "results": hits,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/seed", response_model=Dict[str, Any])
async def seed_search_index_endpoint() -> Dict[str, Any]:
    try:
        result = algolia_search_service.seed_all_entities()
        return {
            "status": "success",
            "message": "Seeded Algolia search index successfully.",
            "details": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Algolia seeding failed: {str(e)}")
